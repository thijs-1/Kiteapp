"""Service for fetching and disk-caching spot satellite map images."""
import math
import os
import re
import threading
from pathlib import Path
from typing import Optional

import httpx

from backend.config import settings

ESRI_EXPORT_URL = (
    "https://server.arcgisonline.com/ArcGIS/rest/services/"
    "World_Imagery/MapServer/export"
)
METERS_PER_DEGREE_LAT = 111320.0


class MapImageService:
    """Fetches satellite images of the box around a spot from Esri's export
    API and caches them on disk, keeping only the most recently used ones.

    Cache hits are served as-is; callers are expected to invoke
    ``refresh_image`` in the background afterwards so the cached image
    converges to Esri's most recent imagery without slowing the response.
    """

    def __init__(
        self,
        cache_dir: Path = None,
        max_entries: int = None,
        half_box_m: float = None,
        size_px: int = None,
    ):
        self.cache_dir = Path(cache_dir or settings.map_image_cache_dir)
        self.max_entries = max_entries or settings.map_image_cache_max_entries
        self.half_box_m = half_box_m or settings.map_image_half_box_m
        self.size_px = size_px or settings.map_image_size_px
        self._lock = threading.Lock()
        # Spot ids with a refresh in flight, to avoid duplicate Esri fetches
        self._refreshing: set = set()

    def get_cached_image(self, spot_id: str) -> Optional[bytes]:
        """Get the cached image for a spot, or None if not cached."""
        path = self._cache_path(spot_id)
        try:
            image = path.read_bytes()
        except OSError:
            return None
        if not image:
            return None
        # Refresh mtime so eviction drops least recently *used*, not written
        os.utime(path)
        return image

    def refresh_image(self, spot_id: str, latitude: float, longitude: float) -> Optional[bytes]:
        """Fetch the latest image from Esri and store it. None on failure."""
        with self._lock:
            if spot_id in self._refreshing:
                return None
            self._refreshing.add(spot_id)
        try:
            image = self._fetch(latitude, longitude)
            if image is None:
                return None
            self._store(spot_id, image)
            return image
        finally:
            with self._lock:
                self._refreshing.discard(spot_id)

    def _cache_path(self, spot_id: str) -> Path:
        safe = re.sub(r"[^A-Za-z0-9._-]", "_", spot_id)
        return self.cache_dir / f"{safe}.jpg"

    def _fetch(self, latitude: float, longitude: float) -> Optional[bytes]:
        lat_delta = self.half_box_m / METERS_PER_DEGREE_LAT
        lng_delta = self.half_box_m / (
            METERS_PER_DEGREE_LAT * math.cos(math.radians(latitude))
        )
        params = {
            "bbox": (
                f"{longitude - lng_delta},{latitude - lat_delta},"
                f"{longitude + lng_delta},{latitude + lat_delta}"
            ),
            "bboxSR": "4326",
            "imageSR": "3857",
            "size": f"{self.size_px},{self.size_px}",
            "format": "jpg",
            "f": "image",
        }
        try:
            response = httpx.get(ESRI_EXPORT_URL, params=params, timeout=15.0)
            response.raise_for_status()
        except httpx.HTTPError:
            return None
        # Esri reports some errors as HTTP 200 with a JSON body
        if not response.headers.get("content-type", "").startswith("image/"):
            return None
        return response.content

    def _store(self, spot_id: str, image: bytes) -> None:
        path = self._cache_path(spot_id)
        with self._lock:
            self.cache_dir.mkdir(parents=True, exist_ok=True)
            tmp = path.with_suffix(".tmp")
            tmp.write_bytes(image)
            tmp.replace(path)
            self._evict()

    def _evict(self) -> None:
        """Delete the least recently used images beyond max_entries."""
        files = sorted(
            self.cache_dir.glob("*.jpg"),
            key=lambda p: p.stat().st_mtime,
            reverse=True,
        )
        for stale in files[self.max_entries:]:
            try:
                stale.unlink()
            except OSError:
                pass
