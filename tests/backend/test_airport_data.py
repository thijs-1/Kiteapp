"""Tests for nearest-airport data flow through repository, service, and routes."""
import pickle
from unittest.mock import MagicMock

import numpy as np
import pandas as pd
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.api.dependencies import get_spot_service
from backend.api.routes import spots as spots_routes
from backend.data.spot_repository import SpotRepository, as_airport_list
from backend.services.spot_service import SpotService


AIRPORT_A = {
    "iata": "AAA",
    "name": "Alpha Intl",
    "municipality": "Alphaville",
    "iso_country": "AA",
    "latitude": 10.5,
    "longitude": 20.5,
    "distance_km": 50.0,
    "duration_minutes": 45.0,
}
AIRPORT_B = {
    "iata": "BBB",
    "name": "Beta Intl",
    "municipality": None,
    "iso_country": "BB",
    "latitude": 11.0,
    "longitude": 21.0,
    "distance_km": 80.0,
    "duration_minutes": 70.0,
}


def _spots_df(airports_column=True):
    df = pd.DataFrame(
        {
            "spot_id": ["s1", "s2", "s3"],
            "name": ["Spot One", "Spot Two", "Spot Three"],
            "latitude": [1.0, 2.0, 3.0],
            "longitude": [4.0, 5.0, 6.0],
            "country": ["Aruba", "Brazil", "Chile"],
        }
    )
    if airports_column:
        # s1 has two airports, s2 none computed, s3 a far one + a NaN-style cell
        # is exercised separately below.
        df["nearest_airports"] = [
            [AIRPORT_A, AIRPORT_B],
            [],
            [{**AIRPORT_A, "iata": "CCC", "distance_km": 200.0}],
        ]
    return df


def _write_spots_pkl(tmp_path, df):
    path = tmp_path / "spots.pkl"
    with open(path, "wb") as f:
        pickle.dump(df, f)
    return path


def _mock_histogram_repo(spot_ids):
    """Histogram repo stub where every spot is 100% kiteable."""
    repo = MagicMock()
    n = len(spot_ids)
    repo.get_range_sums.return_value = np.ones((n, 2))
    repo.get_1d_spot_ids.return_value = list(spot_ids)
    repo.get_1d_bin_mask.return_value = np.array([True, True])
    repo._1d_spot_to_idx = {sid: i for i, sid in enumerate(spot_ids)}
    return repo


def _make_service(tmp_path, airports_column=True):
    df = _spots_df(airports_column=airports_column)
    spot_repo = SpotRepository(spots_file=_write_spots_pkl(tmp_path, df))
    return SpotService(
        spot_repo=spot_repo,
        histogram_repo=_mock_histogram_repo(df["spot_id"]),
    )


class TestAsAirportList:
    def test_none_is_empty(self):
        assert as_airport_list(None) == []

    def test_nan_is_empty(self):
        assert as_airport_list(float("nan")) == []

    def test_empty_list(self):
        assert as_airport_list([]) == []

    def test_list_passthrough(self):
        assert as_airport_list([AIRPORT_A]) == [AIRPORT_A]

    def test_numpy_array_is_listified(self):
        arr = np.array([AIRPORT_A, AIRPORT_B], dtype=object)
        assert as_airport_list(arr) == [AIRPORT_A, AIRPORT_B]


class TestRepositoryMinDistance:
    def test_min_distance_array(self, tmp_path):
        repo = SpotRepository(spots_file=_write_spots_pkl(tmp_path, _spots_df()))
        dist = repo.get_min_airport_distance_array()
        assert dist is not None
        assert dist[0] == pytest.approx(50.0)  # min of 50/80
        assert np.isinf(dist[1])               # no airports computed
        assert dist[2] == pytest.approx(200.0)

    def test_nan_cell_is_inf(self, tmp_path):
        df = _spots_df()
        df["nearest_airports"] = [[AIRPORT_A], float("nan"), None]
        repo = SpotRepository(spots_file=_write_spots_pkl(tmp_path, df))
        dist = repo.get_min_airport_distance_array()
        assert dist[0] == pytest.approx(50.0)
        assert np.isinf(dist[1])
        assert np.isinf(dist[2])

    def test_missing_column(self, tmp_path):
        repo = SpotRepository(
            spots_file=_write_spots_pkl(tmp_path, _spots_df(airports_column=False))
        )
        assert repo.get_min_airport_distance_array() is None
        assert repo.has_airport_data() is False

    def test_has_airport_data(self, tmp_path):
        repo = SpotRepository(spots_file=_write_spots_pkl(tmp_path, _spots_df()))
        assert repo.has_airport_data() is True

    def test_all_empty_lists_means_no_airport_data(self, tmp_path):
        df = _spots_df()
        df["nearest_airports"] = [[], [], []]
        repo = SpotRepository(spots_file=_write_spots_pkl(tmp_path, df))
        assert repo.has_airport_data() is False


class TestServiceFiltering:
    def test_no_airport_filter_returns_all(self, tmp_path):
        service = _make_service(tmp_path)
        result = service.filter_spots(min_percentage=0)
        assert {s.spot_id for s in result} == {"s1", "s2", "s3"}

    def test_airport_filter_excludes_far_and_unknown(self, tmp_path):
        service = _make_service(tmp_path)
        result = service.filter_spots(min_percentage=0, max_airport_distance_km=100)
        # s2 has no computed airports (inf), s3's nearest is 200 km away.
        assert [s.spot_id for s in result] == ["s1"]

    def test_airport_filter_boundary_is_inclusive(self, tmp_path):
        service = _make_service(tmp_path)
        result = service.filter_spots(min_percentage=0, max_airport_distance_km=200)
        assert {s.spot_id for s in result} == {"s1", "s3"}

    def test_airport_filter_ignored_without_column(self, tmp_path):
        service = _make_service(tmp_path, airports_column=False)
        result = service.filter_spots(min_percentage=0, max_airport_distance_km=10)
        assert {s.spot_id for s in result} == {"s1", "s2", "s3"}

    def test_filter_cache_distinguishes_airport_distance(self, tmp_path):
        service = _make_service(tmp_path)
        all_spots = service.filter_spots(min_percentage=0)
        near_only = service.filter_spots(min_percentage=0, max_airport_distance_km=100)
        assert len(all_spots) == 3
        assert len(near_only) == 1

    def test_list_results_carry_no_airports(self, tmp_path):
        service = _make_service(tmp_path)
        result = service.filter_spots(min_percentage=0)
        assert all(not hasattr(s, "nearest_airports") for s in result)
        assert all(
            not hasattr(s, "nearest_airports") for s in service.get_all_spots()
        )


class TestServiceDetailAndMeta:
    def test_get_spot_includes_airports(self, tmp_path):
        service = _make_service(tmp_path)
        spot = service.get_spot("s1")
        assert spot is not None
        assert [a.iata for a in spot.nearest_airports] == ["AAA", "BBB"]
        assert spot.nearest_airports[0].latitude == pytest.approx(10.5)
        assert spot.nearest_airports[0].longitude == pytest.approx(20.5)

    def test_get_spot_without_column(self, tmp_path):
        service = _make_service(tmp_path, airports_column=False)
        spot = service.get_spot("s1")
        assert spot is not None
        assert spot.nearest_airports == []

    def test_meta(self, tmp_path):
        assert _make_service(tmp_path).get_meta().has_airport_data is True
        assert (
            _make_service(tmp_path, airports_column=False).get_meta().has_airport_data
            is False
        )


@pytest.fixture
def client(tmp_path):
    app = FastAPI()
    app.include_router(spots_routes.router)
    service = _make_service(tmp_path)
    app.dependency_overrides[get_spot_service] = lambda: service
    return TestClient(app)


class TestRoutes:
    def test_meta_route_not_shadowed_by_spot_id(self, client):
        # /spots/meta is declared before /spots/{spot_id}; a regression in route
        # order would 404 here (no spot with id "meta").
        resp = client.get("/spots/meta")
        assert resp.status_code == 200
        assert resp.json() == {"has_airport_data": True}

    def test_detail_includes_airports(self, client):
        resp = client.get("/spots/s1")
        assert resp.status_code == 200
        body = resp.json()
        assert [a["iata"] for a in body["nearest_airports"]] == ["AAA", "BBB"]

    def test_unknown_spot_404(self, client):
        assert client.get("/spots/nope").status_code == 404

    def test_list_payload_has_no_airports(self, client):
        resp = client.get("/spots", params={"min_percentage": 0})
        assert resp.status_code == 200
        body = resp.json()
        assert len(body) == 3
        assert all("nearest_airports" not in s for s in body)

    def test_filtered_list_respects_airport_distance(self, client):
        resp = client.get(
            "/spots", params={"min_percentage": 0, "max_airport_distance_km": 100}
        )
        assert resp.status_code == 200
        assert [s["spot_id"] for s in resp.json()] == ["s1"]
