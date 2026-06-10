"""Tests for the airport service."""
import json
from unittest.mock import MagicMock, patch

import numpy as np
import pandas as pd
import pytest
import requests

from data_pipelines.services.airport_service import (
    AirportReference,
    AirportService,
    TransientOSRMError,
    haversine_km,
    load_airports,
)


# ----------------------------------------------------------------------
# Haversine
# ----------------------------------------------------------------------


class TestHaversine:
    def test_zero_distance(self):
        d = haversine_km(40.0, -74.0, np.array([40.0]), np.array([-74.0]))
        assert d[0] == pytest.approx(0.0, abs=1e-6)

    def test_jfk_to_lhr(self):
        # JFK (40.6413, -73.7781) to LHR (51.4700, -0.4543) is ~5550 km.
        d = haversine_km(40.6413, -73.7781, np.array([51.4700]), np.array([-0.4543]))
        assert d[0] == pytest.approx(5540, abs=30)

    def test_antipodal(self):
        # Antipodal points are pi * R apart, ~20015 km.
        d = haversine_km(0.0, 0.0, np.array([0.0]), np.array([180.0]))
        assert d[0] == pytest.approx(20015, abs=10)

    def test_vectorized_matches_scalar(self):
        lats = np.array([10.0, -25.0, 60.0, 0.0])
        lons = np.array([20.0, 80.0, -100.0, 179.0])
        vec = haversine_km(0.0, 0.0, lats, lons)
        scalar = np.array([
            haversine_km(0.0, 0.0, np.array([la]), np.array([lo]))[0]
            for la, lo in zip(lats, lons)
        ])
        np.testing.assert_allclose(vec, scalar, rtol=1e-9)


# ----------------------------------------------------------------------
# load_airports
# ----------------------------------------------------------------------


def _write_airports_csv(tmp_path, rows):
    cols = [
        "type", "name", "iata_code", "iso_country",
        "municipality", "latitude_deg", "longitude_deg",
    ]
    df = pd.DataFrame(rows, columns=cols)
    path = tmp_path / "airports.csv"
    df.to_csv(path, index=False)
    return path


def _row(**overrides):
    base = {
        "type": "large_airport",
        "name": "X Intl",
        "iata_code": "XXX",
        "iso_country": "FR",
        "municipality": "Paris",
        "latitude_deg": 0.0,
        "longitude_deg": 0.0,
    }
    base.update(overrides)
    return base


class TestLoadAirports:
    def test_preserves_metadata(self, tmp_path):
        path = _write_airports_csv(tmp_path, [
            _row(
                iata_code="CDG", name="Charles de Gaulle",
                municipality="Paris", iso_country="FR",
                latitude_deg=49.01, longitude_deg=2.55,
            ),
        ])
        a = load_airports(path)[0]
        assert a == AirportReference(
            iata="CDG",
            name="Charles de Gaulle",
            municipality="Paris",
            iso_country="FR",
            latitude=49.01,
            longitude=2.55,
        )

    def test_loads_all_rows(self, tmp_path):
        # Loader trusts the CSV is pre-filtered: no row-level filtering here.
        path = _write_airports_csv(tmp_path, [
            _row(iata_code="AAA"),
            _row(iata_code="BBB"),
            _row(iata_code="CCC"),
        ])
        airports = load_airports(path)
        assert [a.iata for a in airports] == ["AAA", "BBB", "CCC"]


# ----------------------------------------------------------------------
# AirportService
# ----------------------------------------------------------------------


@pytest.fixture
def airports_csv(tmp_path):
    """Three airports, each on its own meridian along the equator."""
    return _write_airports_csv(tmp_path, [
        _row(iata_code="ONE", name="One Intl", latitude_deg=0.0, longitude_deg=10.0,
             municipality="A", iso_country="AA"),
        _row(iata_code="TWO", name="Two Intl", latitude_deg=0.0, longitude_deg=20.0,
             municipality="B", iso_country="BB"),
        _row(iata_code="THR", name="Three Intl", latitude_deg=0.0, longitude_deg=30.0,
             municipality="C", iso_country="CC"),
    ])


def _make_service(tmp_path, airports_csv, **overrides):
    kwargs = dict(
        airports_csv=airports_csv,
        cache_path=tmp_path / "cache.json",
        osrm_table_url="http://osrm.example/table/v1/driving",
        rate_limit_seconds=0.0,
        timeout=5,
        shortlist_size=3,
        keep_count=2,
        retry_failed=False,
        max_attempts=1,
        retry_backoff_seconds=0.0,
    )
    kwargs.update(overrides)
    return AirportService(**kwargs)


def _table_response(distances_m, durations_s):
    """Build a one-source OSRM /table payload."""
    return {
        "code": "Ok",
        "distances": [distances_m],
        "durations": [durations_s],
    }


class TestShortlist:
    def test_returns_k_in_distance_order(self, tmp_path, airports_csv):
        service = _make_service(tmp_path, airports_csv, shortlist_size=2, keep_count=2)
        result = service.shortlist_nearest(spot_lat=0.0, spot_lon=12.0)
        assert [a.iata for a in result] == ["ONE", "TWO"]


class TestOSRMTable:
    def _airports(self, service, *iatas):
        by_iata = {a.iata: a for a in service.airports}
        return [by_iata[i] for i in iatas]

    def test_parses_response(self, tmp_path, airports_csv):
        service = _make_service(tmp_path, airports_csv)
        fake = MagicMock(status_code=200)
        fake.json.return_value = _table_response([12345.0, 4000.0], [1800.0, 600.0])
        with patch.object(requests, "get", return_value=fake) as mock_get:
            routes, status = service.osrm_table(
                0.0, 15.0, self._airports(service, "ONE", "TWO")
            )
        mock_get.assert_called_once()
        assert status == "ok"
        assert routes == [
            {"distance_km": 12.345, "duration_minutes": 30.0},
            {"distance_km": 4.0, "duration_minutes": 10.0},
        ]

    def test_request_url_has_sources_destinations_annotations(self, tmp_path, airports_csv):
        service = _make_service(tmp_path, airports_csv)
        fake = MagicMock(status_code=200)
        fake.json.return_value = _table_response([0.0, 0.0], [0.0, 0.0])
        with patch.object(requests, "get", return_value=fake) as mock_get:
            service.osrm_table(1.0, 15.0, self._airports(service, "ONE", "TWO"))
        url = mock_get.call_args.args[0]
        # Spot first as lon,lat then the two airports, source 0 -> destinations 1,2.
        assert url.startswith("http://osrm.example/table/v1/driving/15.0,1.0;10.0,0.0;20.0,0.0?")
        assert "sources=0" in url
        assert "destinations=1;2" in url
        assert "annotations=distance,duration" in url

    def test_null_matrix_entry_means_no_route(self, tmp_path, airports_csv):
        service = _make_service(tmp_path, airports_csv)
        fake = MagicMock(status_code=200)
        fake.json.return_value = _table_response([None, 4000.0], [None, 600.0])
        with patch.object(requests, "get", return_value=fake):
            routes, status = service.osrm_table(
                0.0, 15.0, self._airports(service, "ONE", "TWO")
            )
        assert status == "ok"
        assert routes == [None, {"distance_km": 4.0, "duration_minutes": 10.0}]

    def test_non_ok_code_means_no_route_for_all(self, tmp_path, airports_csv):
        service = _make_service(tmp_path, airports_csv)
        fake = MagicMock(status_code=200)
        fake.json.return_value = {"code": "NoTable"}
        with patch.object(requests, "get", return_value=fake):
            routes, status = service.osrm_table(
                0.0, 15.0, self._airports(service, "ONE", "TWO")
            )
        assert status == "ok"
        assert routes == [None, None]

    def test_5xx_is_transient(self, tmp_path, airports_csv):
        service = _make_service(tmp_path, airports_csv, max_attempts=1)
        with patch.object(requests, "get", return_value=MagicMock(status_code=503)):
            routes, status = service.osrm_table(0.0, 15.0, self._airports(service, "ONE"))
        assert (routes, status) == (None, "transient")

    def test_429_is_transient(self, tmp_path, airports_csv):
        service = _make_service(tmp_path, airports_csv, max_attempts=1)
        with patch.object(requests, "get", return_value=MagicMock(status_code=429)):
            routes, status = service.osrm_table(0.0, 15.0, self._airports(service, "ONE"))
        assert (routes, status) == (None, "transient")

    def test_4xx_is_no_route(self, tmp_path, airports_csv):
        # 4xx other than 429 means a definitive client-side problem (bad coordinates,
        # malformed URL); retrying won't help, so cache it as a negative.
        service = _make_service(tmp_path, airports_csv, max_attempts=1)
        with patch.object(requests, "get", return_value=MagicMock(status_code=400)):
            routes, status = service.osrm_table(
                0.0, 15.0, self._airports(service, "ONE", "TWO")
            )
        assert status == "ok"
        assert routes == [None, None]

    def test_connection_error_is_transient(self, tmp_path, airports_csv):
        service = _make_service(tmp_path, airports_csv, max_attempts=1)
        with patch.object(requests, "get", side_effect=requests.ConnectionError):
            routes, status = service.osrm_table(0.0, 15.0, self._airports(service, "ONE"))
        assert (routes, status) == (None, "transient")

    def test_timeout_is_transient(self, tmp_path, airports_csv):
        service = _make_service(tmp_path, airports_csv, max_attempts=1)
        with patch.object(requests, "get", side_effect=requests.Timeout):
            routes, status = service.osrm_table(0.0, 15.0, self._airports(service, "ONE"))
        assert (routes, status) == (None, "transient")

    def test_invalid_json_is_transient(self, tmp_path, airports_csv):
        service = _make_service(tmp_path, airports_csv, max_attempts=1)
        fake = MagicMock(status_code=200)
        fake.json.side_effect = ValueError("not json")
        with patch.object(requests, "get", return_value=fake):
            routes, status = service.osrm_table(0.0, 15.0, self._airports(service, "ONE"))
        assert (routes, status) == (None, "transient")

    def test_matrix_shape_mismatch_is_transient(self, tmp_path, airports_csv):
        service = _make_service(tmp_path, airports_csv, max_attempts=1)
        fake = MagicMock(status_code=200)
        fake.json.return_value = _table_response([1000.0], [60.0])  # 1 entry, 2 expected
        with patch.object(requests, "get", return_value=fake):
            routes, status = service.osrm_table(
                0.0, 15.0, self._airports(service, "ONE", "TWO")
            )
        assert (routes, status) == (None, "transient")

    def test_retries_then_succeeds(self, tmp_path, airports_csv):
        service = _make_service(
            tmp_path, airports_csv,
            max_attempts=3, retry_backoff_seconds=0.5, rate_limit_seconds=0.0,
        )
        success = MagicMock(status_code=200)
        success.json.return_value = _table_response([1000.0], [60.0])
        side_effects = [requests.ConnectionError(), requests.ConnectionError(), success]
        with (
            patch.object(requests, "get", side_effect=side_effects) as mock_get,
            patch("data_pipelines.services.airport_service.time.sleep") as mock_sleep,
        ):
            routes, status = service.osrm_table(0.0, 15.0, self._airports(service, "ONE"))
        assert status == "ok"
        assert routes == [{"distance_km": 1.0, "duration_minutes": 1.0}]
        assert mock_get.call_count == 3
        # Two backoff sleeps with exponential growth: 0.5, 1.0.
        assert [c.args[0] for c in mock_sleep.call_args_list] == [0.5, 1.0]

    def test_retries_exhausted_returns_transient(self, tmp_path, airports_csv):
        service = _make_service(
            tmp_path, airports_csv,
            max_attempts=3, retry_backoff_seconds=0.1, rate_limit_seconds=0.0,
        )
        with (
            patch.object(requests, "get", side_effect=requests.ConnectionError) as mock_get,
            patch("data_pipelines.services.airport_service.time.sleep"),
        ):
            routes, status = service.osrm_table(0.0, 15.0, self._airports(service, "ONE"))
        assert (routes, status) == (None, "transient")
        assert mock_get.call_count == 3

    def test_sends_user_agent(self, tmp_path, airports_csv):
        service = _make_service(tmp_path, airports_csv, max_attempts=1)
        fake = MagicMock(status_code=200)
        fake.json.return_value = _table_response([0.0], [0.0])
        with patch.object(requests, "get", return_value=fake) as mock_get:
            service.osrm_table(0.0, 15.0, self._airports(service, "ONE"))
        headers = mock_get.call_args.kwargs.get("headers") or {}
        assert "kiteapp" in headers.get("User-Agent", "").lower()


class TestThrottle:
    def test_enforces_minimum_gap(self, tmp_path, airports_csv):
        service = _make_service(tmp_path, airports_csv, rate_limit_seconds=1.0)
        airport = service.airports[:1]
        # First call: no prior request, should not sleep.
        # Second call: prior was 0.2s ago -> must sleep ~0.8s.
        times = iter([100.0, 100.2, 100.2])  # consumed by monotonic()
        with (
            patch("data_pipelines.services.airport_service.time.monotonic",
                  side_effect=lambda: next(times)),
            patch("data_pipelines.services.airport_service.time.sleep") as mock_sleep,
            patch.object(requests, "get", return_value=MagicMock(
                status_code=200,
                json=lambda: _table_response([0.0], [0.0]),
            )),
        ):
            service.osrm_table(0.0, 15.0, airport)  # call 1
            service.osrm_table(0.0, 15.0, airport)  # call 2 — must throttle
        assert mock_sleep.called
        slept = mock_sleep.call_args[0][0]
        assert slept == pytest.approx(0.8, abs=1e-6)


class TestCacheRoundtrip:
    def test_roundtrip(self, tmp_path, airports_csv):
        service = _make_service(tmp_path, airports_csv)
        service._cache["spotA:ONE"] = {"distance_km": 1.0, "duration_minutes": 2.0}
        service._cache["spotA:TWO"] = None
        service.save_cache()

        # Fresh service reads it back.
        reloaded = _make_service(tmp_path, airports_csv)
        assert reloaded._cache["spotA:ONE"] == {"distance_km": 1.0, "duration_minutes": 2.0}
        assert reloaded._cache["spotA:TWO"] is None

    def test_retry_failed_drops_nulls(self, tmp_path, airports_csv):
        # Pre-seed cache file with a null entry.
        cache_path = tmp_path / "cache.json"
        cache_path.write_text(json.dumps({
            "spotA:ONE": {"distance_km": 1.0, "duration_minutes": 2.0},
            "spotA:TWO": None,
        }))
        service = _make_service(tmp_path, airports_csv, retry_failed=True)
        assert "spotA:ONE" in service._cache
        assert "spotA:TWO" not in service._cache


class TestComputeForSpot:
    def test_uses_cache_and_ranks_by_duration(self, tmp_path, airports_csv):
        service = _make_service(tmp_path, airports_csv, shortlist_size=3, keep_count=3)
        # All three pre-cached, no OSRM calls expected. Distance and duration
        # orders disagree on purpose: ranking must follow duration.
        service._cache.update({
            "spot1:ONE": {"distance_km": 10.0, "duration_minutes": 50.0},
            "spot1:TWO": {"distance_km": 30.0, "duration_minutes": 20.0},
            "spot1:THR": {"distance_km": 20.0, "duration_minutes": 40.0},
        })
        with patch.object(requests, "get") as mock_get:
            result = service.compute_nearest_airports_for_spot("spot1", 0.0, 15.0)
        mock_get.assert_not_called()
        assert [a["iata"] for a in result] == ["TWO", "THR", "ONE"]
        assert result[0]["duration_minutes"] == 20.0

    def test_results_include_airport_coordinates(self, tmp_path, airports_csv):
        service = _make_service(tmp_path, airports_csv, shortlist_size=3, keep_count=3)
        service._cache["spot1:ONE"] = {"distance_km": 5.0, "duration_minutes": 7.0}
        service._cache["spot1:TWO"] = None
        service._cache["spot1:THR"] = None
        result = service.compute_nearest_airports_for_spot("spot1", 0.0, 15.0)
        assert result == [
            {
                "iata": "ONE",
                "name": "One Intl",
                "municipality": "A",
                "iso_country": "AA",
                "latitude": 0.0,
                "longitude": 10.0,
                "distance_km": 5.0,
                "duration_minutes": 7.0,
            }
        ]

    def test_skips_failed_routes(self, tmp_path, airports_csv):
        service = _make_service(tmp_path, airports_csv, shortlist_size=3, keep_count=3)
        service._cache.update({
            "spot1:ONE": None,                                              # failed
            "spot1:TWO": {"distance_km": 10.0, "duration_minutes": 20.0},
            "spot1:THR": None,                                              # failed
        })
        with patch.object(requests, "get") as mock_get:
            result = service.compute_nearest_airports_for_spot("spot1", 0.0, 15.0)
        mock_get.assert_not_called()
        assert [a["iata"] for a in result] == ["TWO"]

    def test_skips_cache_on_transient_failure(self, tmp_path, airports_csv):
        # When OSRM is down, transient failures must not be persisted as None
        # — otherwise --retry-failed becomes the only escape hatch on the next run.
        service = _make_service(
            tmp_path, airports_csv,
            shortlist_size=3, keep_count=3, max_attempts=1,
        )
        with (
            patch.object(requests, "get", side_effect=requests.ConnectionError),
            patch("data_pipelines.services.airport_service.time.sleep"),
        ):
            result = service.compute_nearest_airports_for_spot("spot1", 0.0, 15.0)
        assert result == []
        assert service._cache == {}

    def test_caches_definitive_no_route(self, tmp_path, airports_csv):
        # OSRM definitively returning null matrix entries should be cached as
        # None so we don't re-query on the next run.
        service = _make_service(
            tmp_path, airports_csv,
            shortlist_size=3, keep_count=3, max_attempts=1,
        )
        fake = MagicMock(status_code=200)
        fake.json.return_value = _table_response([None, None, None], [None, None, None])
        with patch.object(requests, "get", return_value=fake):
            result = service.compute_nearest_airports_for_spot("spot1", 0.0, 15.0)
        assert result == []
        assert service._cache == {
            "spot1:ONE": None,
            "spot1:TWO": None,
            "spot1:THR": None,
        }

    def test_one_table_call_covers_all_misses(self, tmp_path, airports_csv):
        service = _make_service(
            tmp_path, airports_csv, shortlist_size=3, keep_count=3, max_attempts=1,
        )
        service._cache["spot1:ONE"] = {"distance_km": 5.0, "duration_minutes": 7.0}

        fake = MagicMock(status_code=200)
        # Spot at lon 15: shortlist order ONE, TWO, THR -> misses TWO, THR.
        fake.json.return_value = _table_response([10000.0, 30000.0], [600.0, 1800.0])
        with patch.object(requests, "get", return_value=fake) as mock_get:
            result = service.compute_nearest_airports_for_spot("spot1", 0.0, 15.0)
        mock_get.assert_called_once()
        url = mock_get.call_args.args[0]
        # Only the two misses appear as destinations (lon 20 and 30).
        assert "20.0,0.0" in url and "30.0,0.0" in url and "10.0,0.0" not in url
        assert [a["iata"] for a in result] == ["ONE", "TWO", "THR"]
        # Cache is now populated for the misses.
        assert service._cache["spot1:TWO"]["distance_km"] == 10.0
        assert service._cache["spot1:THR"]["distance_km"] == 30.0

    def test_fully_cached_spot_makes_no_requests(self, tmp_path, airports_csv):
        service = _make_service(tmp_path, airports_csv, shortlist_size=3, keep_count=2)
        service._cache.update({
            "spot1:ONE": {"distance_km": 1.0, "duration_minutes": 1.0},
            "spot1:TWO": None,
            "spot1:THR": {"distance_km": 3.0, "duration_minutes": 3.0},
        })
        with patch.object(requests, "get") as mock_get:
            result = service.compute_nearest_airports_for_spot("spot1", 0.0, 15.0)
        mock_get.assert_not_called()
        assert [a["iata"] for a in result] == ["ONE", "THR"]


class TestComputeForDataframe:
    def test_writes_cache_and_returns_series(self, tmp_path, airports_csv):
        service = _make_service(tmp_path, airports_csv, shortlist_size=3, keep_count=2)
        service._cache.update({
            "s1:ONE": {"distance_km": 1.0, "duration_minutes": 1.0},
            "s1:TWO": {"distance_km": 2.0, "duration_minutes": 2.0},
            "s1:THR": {"distance_km": 3.0, "duration_minutes": 3.0},
            "s2:ONE": {"distance_km": 9.0, "duration_minutes": 9.0},
            "s2:TWO": {"distance_km": 4.0, "duration_minutes": 4.0},
            "s2:THR": {"distance_km": 7.0, "duration_minutes": 7.0},
        })
        df = pd.DataFrame([
            {"spot_id": "s1", "latitude": 0.0, "longitude": 5.0},
            {"spot_id": "s2", "latitude": 0.0, "longitude": 25.0},
        ])
        with patch.object(requests, "get") as mock_get:
            series = service.compute_for_dataframe(df, save_every=0)
        mock_get.assert_not_called()
        assert list(series.index) == [0, 1]
        assert [a["iata"] for a in series.iloc[0]] == ["ONE", "TWO"]
        assert [a["iata"] for a in series.iloc[1]] == ["TWO", "THR"]
        # save_cache is called in finally; file should exist.
        assert (tmp_path / "cache.json").exists()
