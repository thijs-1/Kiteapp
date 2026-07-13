"""Tests for temperature/precipitation histograms and time series storage."""
import numpy as np

from data_pipelines.config import TEMPERATURE_BINS, PRECIPITATION_BINS
from data_pipelines.services.histogram_builder import HistogramBuilder
from data_pipelines.services.timeseries_store import TimeseriesStore


def make_hourly_timestamps(start: str, hours: int) -> np.ndarray:
    """Create hourly timestamps starting at midnight of the given date."""
    return np.array([
        np.datetime64(start) + np.timedelta64(h, "h")
        for h in range(hours)
    ])


class TestBuildDailyValueHistogram:
    """Tests for the generic daily value histogram used for weather data."""

    def test_values_land_in_expected_bins(self):
        timestamps = make_hourly_timestamps("2024-06-21", 4)
        # Bins [0, 2.5, 5, 7.5]: values fall in bins 0, 0, 1, 2
        values = np.array([0.0, 2.4, 2.5, 7.4], dtype=np.float32)

        builder = HistogramBuilder(filter_daylight=False)
        hist = builder.build_daily_value_histogram(
            "spot", timestamps, values, bins=[0, 2.5, 5, 7.5]
        )

        assert hist.daily_counts["06-21"].tolist() == [2, 1, 1]

    def test_nan_values_are_excluded(self):
        timestamps = make_hourly_timestamps("2024-06-21", 4)
        values = np.array([1.0, np.nan, np.nan, 2.0], dtype=np.float32)

        builder = HistogramBuilder(filter_daylight=False)
        hist = builder.build_daily_value_histogram(
            "spot", timestamps, values, bins=[0, 2.5, 5]
        )

        assert hist.daily_counts["06-21"].sum() == 2

    def test_daylight_filter_reduces_counts(self):
        # Amsterdam: not all 24 hours are daylight
        latitude, longitude = 52.37, 4.89
        timestamps = make_hourly_timestamps("2024-06-21", 24)
        values = np.full(24, 20.0, dtype=np.float32)

        builder = HistogramBuilder(filter_daylight=True)
        hist = builder.build_daily_temperature_histogram(
            "spot", timestamps, values, latitude, longitude
        )

        total = hist.daily_counts["06-21"].sum()
        assert 0 < total < 24

    def test_temperature_histogram_uses_2_5_degree_bins(self):
        timestamps = make_hourly_timestamps("2024-06-21", 3)
        # 20.0 and 21.0 share the [20, 22.5) bin, 22.5 goes to the next one
        values = np.array([20.0, 21.0, 22.5], dtype=np.float32)

        builder = HistogramBuilder(filter_daylight=False)
        hist = builder.build_daily_temperature_histogram("spot", timestamps, values)

        assert hist.bins == TEMPERATURE_BINS
        bin_20 = TEMPERATURE_BINS.index(20.0)
        counts = hist.daily_counts["06-21"]
        assert counts[bin_20] == 2
        assert counts[bin_20 + 1] == 1
        assert counts.sum() == 3

    def test_temperature_extremes_counted_in_open_ended_bin(self):
        timestamps = make_hourly_timestamps("2024-06-21", 1)
        values = np.array([55.0], dtype=np.float32)  # Above last finite edge (45)

        builder = HistogramBuilder(filter_daylight=False)
        hist = builder.build_daily_temperature_histogram("spot", timestamps, values)

        assert hist.daily_counts["06-21"][-1] == 1

    def test_precipitation_histogram_uses_2_5_mm_bins(self):
        timestamps = make_hourly_timestamps("2024-06-21", 4)
        # Dry hour, drizzle, moderate rain, extreme downpour
        values = np.array([0.0, 1.2, 6.0, 100.0], dtype=np.float32)

        builder = HistogramBuilder(filter_daylight=False)
        hist = builder.build_daily_precipitation_histogram("spot", timestamps, values)

        assert hist.bins == PRECIPITATION_BINS
        counts = hist.daily_counts["06-21"]
        assert counts[0] == 2  # [0, 2.5)
        assert counts[2] == 1  # [5, 7.5)
        assert counts[-1] == 1  # [25, inf)
        assert counts.sum() == 4

    def test_counts_grouped_by_day_of_year(self):
        timestamps = make_hourly_timestamps("2024-06-21", 48)
        values = np.full(48, 15.0, dtype=np.float32)

        builder = HistogramBuilder(filter_daylight=False)
        hist = builder.build_daily_temperature_histogram("spot", timestamps, values)

        assert hist.daily_counts["06-21"].sum() == 24
        assert hist.daily_counts["06-22"].sum() == 24


class TestTimeseriesStoreWeatherVariables:
    """Tests for temperature/precipitation storage in TimeseriesStore."""

    def test_round_trip_with_weather_variables(self, tmp_path):
        store = TimeseriesStore(output_dir=tmp_path)
        time = make_hourly_timestamps("2024-01-01", 3)

        store.append_spot_data(
            "spot",
            time,
            strength=np.array([10, 11, 12], dtype=np.float32),
            direction=np.array([90, 180, 270], dtype=np.float32),
            temperature=np.array([5.0, 6.0, 7.0], dtype=np.float32),
            precipitation=np.array([0.0, 0.5, 1.0], dtype=np.float32),
        )

        data = store.load_spot_data("spot")
        assert data["temperature"].tolist() == [5.0, 6.0, 7.0]
        assert data["precipitation"].tolist() == [0.0, 0.5, 1.0]

    def test_load_legacy_file_without_weather_variables(self, tmp_path):
        store = TimeseriesStore(output_dir=tmp_path)
        time = make_hourly_timestamps("2024-01-01", 2)

        # Simulate a file written before temperature/precipitation existed
        np.savez_compressed(
            store.get_spot_path("spot"),
            time=time,
            strength=np.array([10, 11], dtype=np.float32),
            direction=np.array([90, 180], dtype=np.float32),
        )

        data = store.load_spot_data("spot")
        assert data["temperature"] is None
        assert data["precipitation"] is None
        assert len(data["strength"]) == 2

    def test_append_weather_to_legacy_file_pads_with_nan(self, tmp_path):
        store = TimeseriesStore(output_dir=tmp_path)

        # Legacy chunk: wind only
        time1 = make_hourly_timestamps("2024-01-01", 2)
        store.append_spot_data(
            "spot",
            time1,
            strength=np.array([10, 11], dtype=np.float32),
            direction=np.array([90, 180], dtype=np.float32),
        )

        # New chunk: includes weather variables
        time2 = make_hourly_timestamps("2024-01-01T02", 2)
        store.append_spot_data(
            "spot",
            time2,
            strength=np.array([12, 13], dtype=np.float32),
            direction=np.array([270, 0], dtype=np.float32),
            temperature=np.array([5.0, 6.0], dtype=np.float32),
            precipitation=np.array([0.0, 1.5], dtype=np.float32),
        )

        data = store.load_spot_data("spot")
        assert len(data["time"]) == 4
        # Legacy hours are NaN, new hours have values (sorted by time)
        assert np.isnan(data["temperature"][:2]).all()
        assert data["temperature"][2:].tolist() == [5.0, 6.0]
        assert np.isnan(data["precipitation"][:2]).all()
        assert data["precipitation"][2:].tolist() == [0.0, 1.5]

    def test_append_legacy_chunk_to_weather_file_pads_with_nan(self, tmp_path):
        store = TimeseriesStore(output_dir=tmp_path)

        time1 = make_hourly_timestamps("2024-01-01", 2)
        store.append_spot_data(
            "spot",
            time1,
            strength=np.array([10, 11], dtype=np.float32),
            direction=np.array([90, 180], dtype=np.float32),
            temperature=np.array([5.0, 6.0], dtype=np.float32),
            precipitation=np.array([0.0, 1.5], dtype=np.float32),
        )

        time2 = make_hourly_timestamps("2024-01-01T02", 2)
        store.append_spot_data(
            "spot",
            time2,
            strength=np.array([12, 13], dtype=np.float32),
            direction=np.array([270, 0], dtype=np.float32),
        )

        data = store.load_spot_data("spot")
        assert data["temperature"][:2].tolist() == [5.0, 6.0]
        assert np.isnan(data["temperature"][2:]).all()

    def test_wind_only_files_stay_wind_only(self, tmp_path):
        store = TimeseriesStore(output_dir=tmp_path)
        time = make_hourly_timestamps("2024-01-01", 2)

        store.append_spot_data(
            "spot",
            time,
            strength=np.array([10, 11], dtype=np.float32),
            direction=np.array([90, 180], dtype=np.float32),
        )

        data = store.load_spot_data("spot")
        assert data["temperature"] is None
        assert data["precipitation"] is None
