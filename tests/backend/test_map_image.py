"""Tests for the spot map image service and route."""
import os
from unittest.mock import MagicMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.api.dependencies import get_map_image_service, get_spot_service
from backend.api.routes import spots as spots_routes
from backend.schemas.spot import SpotDetail
from backend.services.map_image_service import MapImageService


JPEG = b"\xff\xd8fake-jpeg-bytes"


def make_service(tmp_path, max_entries=3, refresh_after_days=30.0):
    return MapImageService(
        cache_dir=tmp_path / "map_images",
        max_entries=max_entries,
        refresh_after_days=refresh_after_days,
        half_box_m=500.0,
        size_px=1024,
    )


def age_cached_image(service, spot_id, days):
    """Backdate a cached image's fetched-at mtime by the given number of days."""
    path = service._cache_path(spot_id)
    fetched_at = path.stat().st_mtime - days * 86400
    os.utime(path, (fetched_at, fetched_at))


class TestMapImageService:
    def test_refresh_stores_and_cached_read_returns_it(self, tmp_path, monkeypatch):
        service = make_service(tmp_path)
        monkeypatch.setattr(service, "_fetch", MagicMock(return_value=JPEG))

        assert service.get_cached_image("s1") is None
        assert service.refresh_image("s1", 38.0, -0.5) == JPEG
        assert service.get_cached_image("s1") == JPEG
        assert service._fetch.call_count == 1

    def test_is_stale_tracks_fetch_age_not_reads(self, tmp_path, monkeypatch):
        service = make_service(tmp_path, refresh_after_days=30.0)
        monkeypatch.setattr(service, "_fetch", MagicMock(return_value=JPEG))

        assert service.is_stale("s1")  # not cached yet
        service.refresh_image("s1", 38.0, -0.5)
        assert not service.is_stale("s1")

        age_cached_image(service, "s1", days=31)
        # Serving the image marks it as used but must not reset its age
        assert service.get_cached_image("s1") == JPEG
        assert service.is_stale("s1")
        # A refresh resets the age
        service.refresh_image("s1", 38.0, -0.5)
        assert not service.is_stale("s1")

    def test_fetch_failure_returns_none_and_keeps_old_image(self, tmp_path, monkeypatch):
        service = make_service(tmp_path)
        monkeypatch.setattr(service, "_fetch", MagicMock(return_value=JPEG))
        service.refresh_image("s1", 38.0, -0.5)

        monkeypatch.setattr(service, "_fetch", MagicMock(return_value=None))
        assert service.refresh_image("s1", 38.0, -0.5) is None
        # Failed refresh must not clobber the cached image
        assert service.get_cached_image("s1") == JPEG

    def test_evicts_least_recently_used_beyond_max(self, tmp_path, monkeypatch):
        service = make_service(tmp_path, max_entries=3)
        monkeypatch.setattr(service, "_fetch", MagicMock(return_value=JPEG))

        for i, spot in enumerate(["s1", "s2", "s3"]):
            service.refresh_image(spot, 38.0, -0.5)
            # Spread mtimes so LRU order is unambiguous regardless of fs resolution
            os.utime(service._cache_path(spot), (1000 + i, 1000 + i))

        # Touch s1 (oldest write) via a read, making s2 the least recently used
        os.utime(service._cache_path("s1"), (2000, 2000))
        service.refresh_image("s4", 38.0, -0.5)
        os.utime(service._cache_path("s4"), (3000, 3000))
        service.refresh_image("s5", 38.0, -0.5)

        cached = {p.stem for p in (tmp_path / "map_images").glob("*.jpg")}
        assert cached == {"s1", "s4", "s5"}

    def test_spot_id_is_sanitized_for_filename(self, tmp_path, monkeypatch):
        service = make_service(tmp_path)
        monkeypatch.setattr(service, "_fetch", MagicMock(return_value=JPEG))
        spot_id = "weird/sp ot:id"

        assert service.refresh_image(spot_id, 38.0, -0.5) == JPEG
        assert service.get_cached_image(spot_id) == JPEG
        path = service._cache_path(spot_id)
        assert path.parent == service.cache_dir
        assert "/" not in path.name and " " not in path.name


def make_app(service, spot=None):
    spot_service = MagicMock()
    spot_service.get_spot.return_value = spot
    app = FastAPI()
    app.include_router(spots_routes.router)
    app.dependency_overrides[get_spot_service] = lambda: spot_service
    app.dependency_overrides[get_map_image_service] = lambda: service
    return app


SPOT = SpotDetail(
    spot_id="s1", name="Spot One", latitude=38.0, longitude=-0.5, country="Spain"
)


class TestMapImageRoute:
    def test_unknown_spot_404(self, tmp_path):
        app = make_app(make_service(tmp_path), spot=None)
        response = TestClient(app).get("/spots/nope/map-image")
        assert response.status_code == 404

    def test_cache_miss_fetches_synchronously(self, tmp_path, monkeypatch):
        service = make_service(tmp_path)
        monkeypatch.setattr(service, "_fetch", MagicMock(return_value=JPEG))
        app = make_app(service, spot=SPOT)

        response = TestClient(app).get("/spots/s1/map-image")
        assert response.status_code == 200
        assert response.headers["content-type"] == "image/jpeg"
        assert "max-age" in response.headers["cache-control"]
        assert response.content == JPEG

    def test_stale_cache_hit_serves_cached_and_refreshes_in_background(
        self, tmp_path, monkeypatch
    ):
        service = make_service(tmp_path, refresh_after_days=30.0)
        monkeypatch.setattr(service, "_fetch", MagicMock(return_value=JPEG))
        service.refresh_image("s1", SPOT.latitude, SPOT.longitude)
        age_cached_image(service, "s1", days=31)

        newer = b"\xff\xd8newer-imagery"
        monkeypatch.setattr(service, "_fetch", MagicMock(return_value=newer))
        app = make_app(service, spot=SPOT)

        # Served bytes are the cached ones; TestClient runs background tasks
        # before returning, after which the cache holds the newer image
        response = TestClient(app).get("/spots/s1/map-image")
        assert response.status_code == 200
        assert response.content == JPEG
        assert service._fetch.call_count == 1
        assert service.get_cached_image("s1") == newer

    def test_fresh_cache_hit_does_not_refetch(self, tmp_path, monkeypatch):
        service = make_service(tmp_path, refresh_after_days=30.0)
        monkeypatch.setattr(service, "_fetch", MagicMock(return_value=JPEG))
        service.refresh_image("s1", SPOT.latitude, SPOT.longitude)

        fetch = MagicMock(return_value=b"\xff\xd8newer-imagery")
        monkeypatch.setattr(service, "_fetch", fetch)
        app = make_app(service, spot=SPOT)

        response = TestClient(app).get("/spots/s1/map-image")
        assert response.status_code == 200
        assert response.content == JPEG
        assert fetch.call_count == 0
        assert service.get_cached_image("s1") == JPEG

    def test_cache_miss_with_fetch_failure_502(self, tmp_path, monkeypatch):
        service = make_service(tmp_path)
        monkeypatch.setattr(service, "_fetch", MagicMock(return_value=None))
        app = make_app(service, spot=SPOT)

        response = TestClient(app).get("/spots/s1/map-image")
        assert response.status_code == 502
