"""Service for computing driving distance from spots to nearest airports.

Pipeline:
1. Load OurAirports CSV, filter to large_airport rows with non-empty IATA.
2. For each spot, take HAVERSINE_SHORTLIST nearest airports by great-circle distance.
3. Query OSRM public demo server for driving distance/duration to each candidate.
4. Keep the NEAREST_AIRPORTS_COUNT shortest by driving distance.

Routes are cached on disk so the run is resumable. A null cache entry means a
previous attempt failed (no route, OSRM error); these are skipped on rerun
unless ``retry_failed=True``.
"""
import json
import math
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import numpy as np
import pandas as pd
import requests
from tqdm import tqdm

from data_pipelines.config import (
    HAVERSINE_SHORTLIST,
    NEAREST_AIRPORTS_COUNT,
    OSRM_RATE_LIMIT_SECONDS,
    OSRM_REQUEST_TIMEOUT,
)


EARTH_RADIUS_KM = 6371.0088


@dataclass(frozen=True)
class AirportReference:
    """One filtered OurAirports row."""

    iata: str
    name: str
    municipality: Optional[str]
    iso_country: Optional[str]
    latitude: float
    longitude: float


def haversine_km(
    lat1: float,
    lon1: float,
    lats: np.ndarray,
    lons: np.ndarray,
) -> np.ndarray:
    """Great-circle distance in km between (lat1, lon1) and arrays (lats, lons)."""
    lat1_r = math.radians(lat1)
    lon1_r = math.radians(lon1)
    lats_r = np.radians(lats)
    lons_r = np.radians(lons)
    dlat = lats_r - lat1_r
    dlon = lons_r - lon1_r
    a = np.sin(dlat / 2.0) ** 2 + math.cos(lat1_r) * np.cos(lats_r) * np.sin(dlon / 2.0) ** 2
    c = 2.0 * np.arcsin(np.sqrt(np.clip(a, 0.0, 1.0)))
    return EARTH_RADIUS_KM * c


def load_airports(csv_path: Path) -> List[AirportReference]:
    """Load OurAirports CSV and filter to large_airport rows with IATA codes."""
    df = pd.read_csv(csv_path, low_memory=False)
    df = df[df["type"] == "large_airport"]
    iata = df["iata_code"].fillna("").astype(str).str.strip()
    df = df[iata != ""]
    df = df.dropna(subset=["latitude_deg", "longitude_deg"])

    airports: List[AirportReference] = []
    for _, row in df.iterrows():
        airports.append(
            AirportReference(
                iata=str(row["iata_code"]).strip(),
                name=str(row["name"]),
                municipality=(str(row["municipality"]) if pd.notna(row["municipality"]) else None),
                iso_country=(str(row["iso_country"]) if pd.notna(row["iso_country"]) else None),
                latitude=float(row["latitude_deg"]),
                longitude=float(row["longitude_deg"]),
            )
        )
    return airports


class AirportService:
    """Computes nearest airports + driving distance per spot."""

    def __init__(
        self,
        airports_csv: Path,
        cache_path: Path,
        osrm_base_url: str,
        rate_limit_seconds: float = OSRM_RATE_LIMIT_SECONDS,
        timeout: int = OSRM_REQUEST_TIMEOUT,
        shortlist_size: int = HAVERSINE_SHORTLIST,
        keep_count: int = NEAREST_AIRPORTS_COUNT,
        retry_failed: bool = False,
    ) -> None:
        self.airports = load_airports(airports_csv)
        self._lats = np.array([a.latitude for a in self.airports], dtype=np.float64)
        self._lons = np.array([a.longitude for a in self.airports], dtype=np.float64)
        self.cache_path = cache_path
        self.osrm_base_url = osrm_base_url.rstrip("/")
        self.rate_limit_seconds = rate_limit_seconds
        self.timeout = timeout
        self.shortlist_size = min(shortlist_size, len(self.airports))
        self.keep_count = keep_count
        self.retry_failed = retry_failed
        self._last_request_ts: Optional[float] = None
        self._cache: Dict[str, Optional[Dict[str, float]]] = self._load_cache()

    # ------------------------------------------------------------------
    # Cache I/O
    # ------------------------------------------------------------------

    def _load_cache(self) -> Dict[str, Optional[Dict[str, float]]]:
        if not self.cache_path.exists():
            return {}
        try:
            with open(self.cache_path, "r") as f:
                cache = json.load(f)
        except (json.JSONDecodeError, OSError):
            return {}
        if self.retry_failed:
            return {k: v for k, v in cache.items() if v is not None}
        return cache

    def save_cache(self) -> None:
        self.cache_path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.cache_path.with_suffix(self.cache_path.suffix + ".tmp")
        with open(tmp, "w") as f:
            json.dump(self._cache, f)
        tmp.replace(self.cache_path)

    # ------------------------------------------------------------------
    # Geo + routing primitives
    # ------------------------------------------------------------------

    def shortlist_nearest(self, spot_lat: float, spot_lon: float) -> List[AirportReference]:
        """Return ``shortlist_size`` airports closest to the spot by great-circle distance."""
        distances = haversine_km(spot_lat, spot_lon, self._lats, self._lons)
        k = self.shortlist_size
        idx = np.argpartition(distances, k - 1)[:k]
        idx = idx[np.argsort(distances[idx])]
        return [self.airports[i] for i in idx]

    def _throttle(self) -> None:
        if self._last_request_ts is None:
            return
        elapsed = time.monotonic() - self._last_request_ts
        gap = self.rate_limit_seconds - elapsed
        if gap > 0:
            time.sleep(gap)

    def osrm_route(
        self,
        spot_lat: float,
        spot_lon: float,
        ap_lat: float,
        ap_lon: float,
    ) -> Optional[Dict[str, float]]:
        """Query OSRM for one route. Returns distance_km/duration_minutes or None."""
        url = (
            f"{self.osrm_base_url}/"
            f"{spot_lon},{spot_lat};{ap_lon},{ap_lat}?overview=false"
        )
        self._throttle()
        try:
            resp = requests.get(url, timeout=self.timeout)
            self._last_request_ts = time.monotonic()
            if resp.status_code != 200:
                return None
            payload = resp.json()
        except (requests.RequestException, ValueError):
            self._last_request_ts = time.monotonic()
            return None

        if payload.get("code") != "Ok":
            return None
        routes = payload.get("routes") or []
        if not routes:
            return None
        route = routes[0]
        return {
            "distance_km": float(route["distance"]) / 1000.0,
            "duration_minutes": float(route["duration"]) / 60.0,
        }

    # ------------------------------------------------------------------
    # Per-spot orchestration
    # ------------------------------------------------------------------

    def compute_nearest_airports_for_spot(
        self,
        spot_id: str,
        spot_lat: float,
        spot_lon: float,
    ) -> List[Dict[str, object]]:
        """Compute up to ``keep_count`` nearest airports by driving distance for one spot."""
        candidates = self.shortlist_nearest(spot_lat, spot_lon)
        scored: List[Tuple[float, AirportReference, Dict[str, float]]] = []

        for airport in candidates:
            cache_key = f"{spot_id}:{airport.iata}"
            if cache_key in self._cache:
                route = self._cache[cache_key]
            else:
                route = self.osrm_route(spot_lat, spot_lon, airport.latitude, airport.longitude)
                self._cache[cache_key] = route

            if route is None:
                continue
            scored.append((route["distance_km"], airport, route))

        scored.sort(key=lambda item: item[0])

        results: List[Dict[str, object]] = []
        for _, airport, route in scored[: self.keep_count]:
            results.append(
                {
                    "iata": airport.iata,
                    "name": airport.name,
                    "municipality": airport.municipality,
                    "iso_country": airport.iso_country,
                    "distance_km": round(route["distance_km"], 2),
                    "duration_minutes": round(route["duration_minutes"], 1),
                }
            )
        return results

    def compute_for_dataframe(
        self,
        df: pd.DataFrame,
        save_every: int = 25,
    ) -> pd.Series:
        """Compute ``nearest_airports`` for each row in ``df``. Resumable via cache.

        Returns a Series of ``list[dict]`` aligned to ``df.index``.
        """
        results: List[List[Dict[str, object]]] = []
        try:
            for i, (_, row) in enumerate(
                tqdm(df.iterrows(), total=len(df), desc="Routing to airports")
            ):
                results.append(
                    self.compute_nearest_airports_for_spot(
                        spot_id=str(row["spot_id"]),
                        spot_lat=float(row["latitude"]),
                        spot_lon=float(row["longitude"]),
                    )
                )
                if save_every and (i + 1) % save_every == 0:
                    self.save_cache()
        finally:
            self.save_cache()

        return pd.Series(results, index=df.index)
