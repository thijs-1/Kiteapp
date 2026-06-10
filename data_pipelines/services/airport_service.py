"""Service for computing driving distance from spots to nearest airports.

Pipeline:
1. Load the pre-filtered airports CSV (large/medium airports with scheduled
   service and IATA codes; see scripts/build_airports_csv.py).
2. For each spot, take HAVERSINE_SHORTLIST nearest airports by great-circle distance.
3. Query the OSRM /table service for driving distance/duration from the spot to
   all uncached candidates in a single request.
4. Keep the NEAREST_AIRPORTS_COUNT shortest by driving duration.

Routes are cached on disk so the run is resumable. A null cache entry means a
previous attempt definitively found no route; these are skipped on rerun
unless ``retry_failed=True``. Transient failures (network, 5xx, 429) are never
cached, so the next run retries them automatically.
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
    OSRM_MAX_ATTEMPTS,
    OSRM_RATE_LIMIT_SECONDS,
    OSRM_REQUEST_TIMEOUT,
    OSRM_RETRY_BACKOFF_SECONDS,
)


EARTH_RADIUS_KM = 6371.0088
OSRM_USER_AGENT = "kiteapp-airport-enrichment/1.0"


class TransientOSRMError(Exception):
    """OSRM request failed in a way that may succeed on retry (network, 5xx, 429, bad JSON)."""


@dataclass(frozen=True)
class AirportReference:
    """One row from the pre-filtered airports CSV."""

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
    """Load the pre-filtered airports CSV.

    The CSV is expected to already contain only scheduled-service airports with
    non-empty IATA codes and valid coordinates (see scripts/build_airports_csv.py).
    """
    df = pd.read_csv(csv_path)
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
        osrm_table_url: str,
        rate_limit_seconds: float = OSRM_RATE_LIMIT_SECONDS,
        timeout: int = OSRM_REQUEST_TIMEOUT,
        shortlist_size: int = HAVERSINE_SHORTLIST,
        keep_count: int = NEAREST_AIRPORTS_COUNT,
        retry_failed: bool = False,
        max_attempts: int = OSRM_MAX_ATTEMPTS,
        retry_backoff_seconds: float = OSRM_RETRY_BACKOFF_SECONDS,
    ) -> None:
        self.airports = load_airports(airports_csv)
        self._lats = np.array([a.latitude for a in self.airports], dtype=np.float64)
        self._lons = np.array([a.longitude for a in self.airports], dtype=np.float64)
        self.cache_path = cache_path
        self.osrm_table_url = osrm_table_url.rstrip("/")
        self.rate_limit_seconds = rate_limit_seconds
        self.timeout = timeout
        self.shortlist_size = min(shortlist_size, len(self.airports))
        self.keep_count = keep_count
        self.retry_failed = retry_failed
        self.max_attempts = max_attempts
        self.retry_backoff_seconds = retry_backoff_seconds
        self._last_request_ts: Optional[float] = None
        self._cache: Dict[str, Optional[Dict[str, float]]] = self._load_cache()

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

    def _table_request_once(self, url: str, n_destinations: int) -> List[Optional[Dict[str, float]]]:
        """Single OSRM /table request.

        Returns one entry per destination: a route dict, or None where OSRM
        found no route (null matrix entry, or a definitive non-Ok response).
        Raises ``TransientOSRMError`` on retryable failures (network errors,
        5xx, 429, malformed JSON).
        """
        self._throttle()
        try:
            resp = requests.get(
                url,
                timeout=self.timeout,
                headers={"User-Agent": OSRM_USER_AGENT},
            )
        except requests.RequestException as e:
            self._last_request_ts = time.monotonic()
            raise TransientOSRMError(str(e)) from e
        self._last_request_ts = time.monotonic()

        if resp.status_code == 429 or resp.status_code >= 500:
            raise TransientOSRMError(f"HTTP {resp.status_code}")
        if resp.status_code != 200:
            return [None] * n_destinations

        try:
            payload = resp.json()
        except ValueError as e:
            raise TransientOSRMError(f"Invalid JSON: {e}") from e

        if payload.get("code") != "Ok":
            return [None] * n_destinations
        distances = (payload.get("distances") or [[]])[0]
        durations = (payload.get("durations") or [[]])[0]
        if len(distances) != n_destinations or len(durations) != n_destinations:
            raise TransientOSRMError(
                f"Matrix shape mismatch: expected {n_destinations} destinations, "
                f"got {len(distances)} distances / {len(durations)} durations"
            )

        results: List[Optional[Dict[str, float]]] = []
        for dist, dur in zip(distances, durations):
            if dist is None or dur is None:
                results.append(None)
            else:
                results.append(
                    {
                        "distance_km": float(dist) / 1000.0,
                        "duration_minutes": float(dur) / 60.0,
                    }
                )
        return results

    def osrm_table(
        self,
        spot_lat: float,
        spot_lon: float,
        airports: List[AirportReference],
    ) -> Tuple[Optional[List[Optional[Dict[str, float]]]], str]:
        """Query OSRM /table for spot -> airports routes, retrying transient failures.

        Returns ``(routes, status)`` where ``routes`` has one entry per airport
        (route dict or None for no-route) and ``status`` is:
            ``"ok"``        — routes populated; per-airport None means OSRM
                              definitively found no route. Safe to cache.
            ``"transient"`` — retries exhausted on a recoverable failure;
                              ``routes`` is None. Caller should NOT cache; the
                              next pipeline run will retry.
        """
        coords = ";".join(
            [f"{spot_lon},{spot_lat}"] + [f"{a.longitude},{a.latitude}" for a in airports]
        )
        destinations = ";".join(str(i + 1) for i in range(len(airports)))
        url = (
            f"{self.osrm_table_url}/{coords}"
            f"?sources=0&destinations={destinations}&annotations=distance,duration"
        )
        backoff = self.retry_backoff_seconds
        for attempt in range(self.max_attempts):
            try:
                return self._table_request_once(url, len(airports)), "ok"
            except TransientOSRMError:
                if attempt + 1 < self.max_attempts:
                    time.sleep(backoff)
                    backoff *= 2
        return None, "transient"

    def compute_nearest_airports_for_spot(
        self,
        spot_id: str,
        spot_lat: float,
        spot_lon: float,
    ) -> List[Dict[str, object]]:
        """Compute up to ``keep_count`` nearest airports by driving duration for one spot."""
        candidates = self.shortlist_nearest(spot_lat, spot_lon)

        # One /table request covers every uncached candidate for this spot.
        misses = [a for a in candidates if f"{spot_id}:{a.iata}" not in self._cache]
        if misses:
            routes, status = self.osrm_table(spot_lat, spot_lon, misses)
            if status == "ok":
                for airport, route in zip(misses, routes):
                    self._cache[f"{spot_id}:{airport.iata}"] = route
            # On "transient" the misses stay uncached so the next run retries them.

        scored: List[Tuple[float, AirportReference, Dict[str, float]]] = []
        for airport in candidates:
            route = self._cache.get(f"{spot_id}:{airport.iata}")
            if route is None:
                continue
            scored.append((route["duration_minutes"], airport, route))

        scored.sort(key=lambda item: item[0])

        results: List[Dict[str, object]] = []
        for _, airport, route in scored[: self.keep_count]:
            results.append(
                {
                    "iata": airport.iata,
                    "name": airport.name,
                    "municipality": airport.municipality,
                    "iso_country": airport.iso_country,
                    "latitude": airport.latitude,
                    "longitude": airport.longitude,
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
