"""Tests for the weather histogram repository, service, and API route."""
import pickle

import numpy as np
import pytest
from fastapi.testclient import TestClient

from backend.data.weather_repository import WeatherHistogramRepository
from backend.services.weather_service import WeatherService, _sanitize_bins_for_json


DAYS = ["01-01", "01-02", "01-03"]
TEMP_BINS = [0.0, 2.5, 5.0, float("inf")]
PRECIP_BINS = [0.0, 2.5, float("inf")]


@pytest.fixture
def weather_files(tmp_path):
    """Write small temperature/precipitation histogram pickles."""
    temp_data = np.zeros((1, len(DAYS), len(TEMP_BINS) - 1), dtype=np.float32)
    temp_data[0, 0] = [5, 3, 2]  # 01-01
    temp_data[0, 1] = [0, 8, 2]  # 01-02

    temp_file = tmp_path / "histograms_temperature.pkl"
    with open(temp_file, "wb") as f:
        pickle.dump({
            "spot_ids": ["spot1"],
            "bins": TEMP_BINS,
            "days": DAYS,
            "data": temp_data,
        }, f)

    precip_data = np.zeros((1, len(DAYS), len(PRECIP_BINS) - 1), dtype=np.float32)
    precip_data[0, 0] = [9, 1]

    precip_file = tmp_path / "histograms_precipitation.pkl"
    with open(precip_file, "wb") as f:
        pickle.dump({
            "spot_ids": ["spot1"],
            "bins": PRECIP_BINS,
            "days": DAYS,
            "data": precip_data,
        }, f)

    return temp_file, precip_file


@pytest.fixture
def weather_service(weather_files):
    temp_file, precip_file = weather_files
    repo = WeatherHistogramRepository(
        temperature_file=temp_file,
        precipitation_file=precip_file,
    )
    return WeatherService(weather_repo=repo)


class TestWeatherService:
    def test_temperature_histograms_returned(self, weather_service):
        result = weather_service.get_daily_histograms("spot1", "temperature")

        assert result["spot_id"] == "spot1"
        assert result["variable"] == "temperature"
        assert result["unit"] == "celsius"
        assert result["daily_data"]["01-01"] == [5, 3, 2]
        assert result["daily_data"]["01-02"] == [0, 8, 2]

    def test_precipitation_histograms_returned(self, weather_service):
        result = weather_service.get_daily_histograms("spot1", "precipitation")

        assert result["unit"] == "mm"
        assert result["daily_data"]["01-01"] == [9, 1]

    def test_infinite_bin_edge_is_sanitized(self, weather_service):
        result = weather_service.get_daily_histograms("spot1", "temperature")

        # [0, 2.5, 5, inf] -> inf replaced by extending one bin width
        assert result["bins"] == [0.0, 2.5, 5.0, 7.5]

    def test_date_range_filters_days(self, weather_service):
        result = weather_service.get_daily_histograms(
            "spot1", "temperature", start_date="01-02", end_date="01-02"
        )

        assert list(result["daily_data"].keys()) == ["01-02"]

    def test_unknown_spot_returns_none(self, weather_service):
        assert weather_service.get_daily_histograms("nope", "temperature") is None

    def test_missing_file_returns_none(self, tmp_path):
        repo = WeatherHistogramRepository(
            temperature_file=tmp_path / "missing_temp.pkl",
            precipitation_file=tmp_path / "missing_precip.pkl",
        )
        service = WeatherService(weather_repo=repo)
        assert service.get_daily_histograms("spot1", "temperature") is None


class TestSanitizeBins:
    def test_negative_infinity_extends_below(self):
        bins = [float("-inf"), 0.0, 2.5, float("inf")]
        assert _sanitize_bins_for_json(bins) == [-2.5, 0.0, 2.5, 5.0]

    def test_finite_bins_unchanged(self):
        bins = [0.0, 2.5, 5.0]
        assert _sanitize_bins_for_json(bins) == [0.0, 2.5, 5.0]


class TestWeatherRoute:
    @pytest.fixture
    def client(self, weather_files):
        from backend.main import app
        from backend.api.dependencies import get_weather_service

        temp_file, precip_file = weather_files
        repo = WeatherHistogramRepository(
            temperature_file=temp_file,
            precipitation_file=precip_file,
        )
        service = WeatherService(weather_repo=repo)
        app.dependency_overrides[get_weather_service] = lambda: service
        yield TestClient(app)
        app.dependency_overrides.pop(get_weather_service, None)

    def test_get_temperature_daily(self, client):
        response = client.get("/spots/spot1/weather/temperature/daily")

        assert response.status_code == 200
        body = response.json()
        assert body["variable"] == "temperature"
        assert body["unit"] == "celsius"
        assert body["daily_data"]["01-01"] == [5, 3, 2]

    def test_get_precipitation_daily(self, client):
        response = client.get("/spots/spot1/weather/precipitation/daily")

        assert response.status_code == 200
        assert response.json()["unit"] == "mm"

    def test_invalid_variable_rejected(self, client):
        response = client.get("/spots/spot1/weather/humidity/daily")
        assert response.status_code == 422

    def test_unknown_spot_404(self, client):
        response = client.get("/spots/ghost/weather/temperature/daily")
        assert response.status_code == 404
