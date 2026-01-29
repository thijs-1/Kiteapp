"""Tests for histogram builder with daylight filtering."""
import numpy as np
import pytest

from data_pipelines.services.histogram_builder import HistogramBuilder


class TestHistogramBuilderDaylightFiltering:
    """Tests for daylight filtering in HistogramBuilder."""

    def create_sample_data(self, hours: int = 24 * 10):
        """Create sample wind data for testing."""
        # Create hourly timestamps for multiple days starting June 21
        timestamps = np.array([
            np.datetime64(f"2024-06-21") + np.timedelta64(h, 'h')
            for h in range(hours)
        ])

        # Create wind strength (varying from 5-20 knots)
        wind_strength = np.random.uniform(5, 20, len(timestamps)).astype(np.float32)

        # Create wind direction (varying from 0-360 degrees)
        wind_direction = np.random.uniform(0, 360, len(timestamps)).astype(np.float32)

        return timestamps, wind_strength, wind_direction

    def test_filter_daylight_enabled_reduces_data(self):
        """Test that enabling daylight filter reduces the number of data points."""
        # Amsterdam coordinates
        latitude = 52.37
        longitude = 4.89

        timestamps, wind_strength, wind_direction = self.create_sample_data(hours=24)

        # Build histogram without filtering
        builder_no_filter = HistogramBuilder(filter_daylight=False)
        hist_1d_no_filter = builder_no_filter.build_daily_1d_histogram(
            "test_spot", timestamps, wind_strength
        )

        # Build histogram with filtering
        builder_with_filter = HistogramBuilder(filter_daylight=True)
        hist_1d_with_filter = builder_with_filter.build_daily_1d_histogram(
            "test_spot", timestamps, wind_strength, latitude, longitude
        )

        # Get total counts for the day
        day = "06-21"
        total_no_filter = hist_1d_no_filter.daily_counts[day].sum()
        total_with_filter = hist_1d_with_filter.daily_counts[day].sum()

        # With filtering, there should be fewer data points
        assert total_with_filter < total_no_filter
        # But there should still be some data (not all filtered out)
        assert total_with_filter > 0

    def test_filter_daylight_disabled_includes_all_hours(self):
        """Test that disabling daylight filter includes all 24 hours."""
        latitude = 52.37
        longitude = 4.89

        timestamps, wind_strength, wind_direction = self.create_sample_data(hours=24)

        builder = HistogramBuilder(filter_daylight=False)
        hist_1d = builder.build_daily_1d_histogram(
            "test_spot", timestamps, wind_strength, latitude, longitude
        )

        # All 24 data points should be included
        day = "06-21"
        total = hist_1d.daily_counts[day].sum()
        assert total == 24

    def test_filter_daylight_without_coordinates_includes_all(self):
        """Test that without coordinates, all hours are included."""
        timestamps, wind_strength, wind_direction = self.create_sample_data(hours=24)

        builder = HistogramBuilder(filter_daylight=True)
        # Don't provide coordinates
        hist_1d = builder.build_daily_1d_histogram(
            "test_spot", timestamps, wind_strength
        )

        # All 24 data points should be included (no filtering without coords)
        day = "06-21"
        total = hist_1d.daily_counts[day].sum()
        assert total == 24

    def test_build_histograms_applies_filter_once(self):
        """Test that build_histograms applies filter correctly."""
        latitude = 52.37
        longitude = 4.89

        timestamps, wind_strength, wind_direction = self.create_sample_data(hours=48)

        builder = HistogramBuilder(filter_daylight=True)
        hist_1d, hist_2d = builder.build_histograms(
            "test_spot", timestamps, wind_strength, wind_direction,
            latitude, longitude
        )

        # Both histograms should have data for the same days
        assert set(hist_1d.daily_counts.keys()) == set(hist_2d.daily_counts.keys())

        # Both should have filtered data (less than 24 hours per day)
        for day in hist_1d.daily_counts.keys():
            total_1d = int(hist_1d.daily_counts[day].sum())
            assert 0 < total_1d < 24, f"Expected filtered data for {day}, got {total_1d}"

            # 2D histogram should have similar counts (may differ slightly due to
            # direction values at bin edges being excluded in histogram2d)
            total_2d = int(hist_2d.daily_counts[day].sum())
            assert abs(total_1d - total_2d) <= 2, \
                f"Counts differ too much for {day}: 1D={total_1d}, 2D={total_2d}"

    def test_2d_histogram_with_daylight_filter(self):
        """Test 2D histogram building with daylight filter."""
        latitude = 52.37
        longitude = 4.89

        timestamps, wind_strength, wind_direction = self.create_sample_data(hours=24)

        builder = HistogramBuilder(filter_daylight=True)
        hist_2d = builder.build_daily_2d_histogram(
            "test_spot", timestamps, wind_strength, wind_direction,
            latitude, longitude
        )

        day = "06-21"
        total = hist_2d.daily_counts[day].sum()

        # Should have fewer than 24 data points
        assert total < 24
        assert total > 0

    def test_same_location_different_seasons(self):
        """Test that the same location has different daylight hours in different seasons."""
        # Amsterdam (mid-latitude, close to UTC)
        latitude = 52.37
        longitude = 4.89

        builder = HistogramBuilder(filter_daylight=True)

        # Summer day timestamps
        summer_ts = np.array([
            np.datetime64(f"2024-06-21") + np.timedelta64(h, 'h')
            for h in range(24)
        ])
        summer_strength = np.ones(24, dtype=np.float32) * 10

        # Winter day timestamps
        winter_ts = np.array([
            np.datetime64(f"2024-12-21") + np.timedelta64(h, 'h')
            for h in range(24)
        ])
        winter_strength = np.ones(24, dtype=np.float32) * 10

        hist_summer = builder.build_daily_1d_histogram(
            "amsterdam", summer_ts, summer_strength, latitude, longitude
        )
        hist_winter = builder.build_daily_1d_histogram(
            "amsterdam", winter_ts, winter_strength, latitude, longitude
        )

        total_summer = hist_summer.daily_counts["06-21"].sum()
        total_winter = hist_winter.daily_counts["12-21"].sum()

        # Summer should have more daylight hours than winter at mid-latitudes
        assert total_summer > total_winter
        # Both should have some data
        assert total_summer > 0
        assert total_winter > 0

    def test_winter_vs_summer_daylight_hours(self):
        """Test that summer has more daylight hours than winter."""
        latitude = 52.37
        longitude = 4.89

        # Summer data (June 21)
        summer_timestamps = np.array([
            np.datetime64(f"2024-06-21") + np.timedelta64(h, 'h')
            for h in range(24)
        ])

        # Winter data (December 21)
        winter_timestamps = np.array([
            np.datetime64(f"2024-12-21") + np.timedelta64(h, 'h')
            for h in range(24)
        ])

        wind_strength = np.ones(24, dtype=np.float32) * 10
        wind_direction = np.ones(24, dtype=np.float32) * 180

        builder = HistogramBuilder(filter_daylight=True)

        hist_summer = builder.build_daily_1d_histogram(
            "test_spot", summer_timestamps, wind_strength, latitude, longitude
        )
        hist_winter = builder.build_daily_1d_histogram(
            "test_spot", winter_timestamps, wind_strength, latitude, longitude
        )

        summer_hours = hist_summer.daily_counts["06-21"].sum()
        winter_hours = hist_winter.daily_counts["12-21"].sum()

        # Summer should have significantly more daylight hours
        assert summer_hours > winter_hours


class TestHistogramBuilderAccumulateWithDaylight:
    """Tests for accumulate method with daylight filtering."""

    def test_accumulate_with_coordinates(self):
        """Test accumulate method with coordinates for daylight filtering."""
        latitude = 52.37
        longitude = 4.89

        timestamps = np.array([
            np.datetime64(f"2024-06-21") + np.timedelta64(h, 'h')
            for h in range(24)
        ])
        wind_strength = np.ones(24, dtype=np.float32) * 10
        wind_direction = np.ones(24, dtype=np.float32) * 180

        builder = HistogramBuilder(filter_daylight=True)
        builder.accumulate(
            "test_spot", timestamps, wind_strength, wind_direction,
            latitude, longitude
        )

        hist_1d = builder.get_accumulated_1d("test_spot")
        total = hist_1d.daily_counts["06-21"].sum()

        # Should have filtered some hours
        assert total < 24
        assert total > 0

    def test_register_spot_coordinates(self):
        """Test registering spot coordinates for accumulation."""
        latitude = 52.37
        longitude = 4.89

        timestamps = np.array([
            np.datetime64(f"2024-06-21") + np.timedelta64(h, 'h')
            for h in range(24)
        ])
        wind_strength = np.ones(24, dtype=np.float32) * 10
        wind_direction = np.ones(24, dtype=np.float32) * 180

        builder = HistogramBuilder(filter_daylight=True)

        # Register coordinates first
        builder.register_spot_coordinates("test_spot", latitude, longitude)

        # Then accumulate without passing coordinates
        builder.accumulate("test_spot", timestamps, wind_strength, wind_direction)

        hist_1d = builder.get_accumulated_1d("test_spot")
        total = hist_1d.daily_counts["06-21"].sum()

        # Should have filtered some hours using registered coordinates
        assert total < 24
        assert total > 0

    def test_accumulate_multiple_chunks(self):
        """Test accumulating multiple chunks with daylight filtering."""
        latitude = 52.37
        longitude = 4.89

        builder = HistogramBuilder(filter_daylight=True)
        builder.register_spot_coordinates("test_spot", latitude, longitude)

        # First chunk: June 21
        timestamps1 = np.array([
            np.datetime64(f"2024-06-21") + np.timedelta64(h, 'h')
            for h in range(24)
        ])
        wind_strength1 = np.ones(24, dtype=np.float32) * 10
        wind_direction1 = np.ones(24, dtype=np.float32) * 180
        builder.accumulate("test_spot", timestamps1, wind_strength1, wind_direction1)

        # Second chunk: June 22
        timestamps2 = np.array([
            np.datetime64(f"2024-06-22") + np.timedelta64(h, 'h')
            for h in range(24)
        ])
        wind_strength2 = np.ones(24, dtype=np.float32) * 15
        wind_direction2 = np.ones(24, dtype=np.float32) * 90
        builder.accumulate("test_spot", timestamps2, wind_strength2, wind_direction2)

        hist_1d = builder.get_accumulated_1d("test_spot")

        # Both days should have data
        assert "06-21" in hist_1d.daily_counts
        assert "06-22" in hist_1d.daily_counts

        # Both should have filtered data (less than 24 hours each)
        assert hist_1d.daily_counts["06-21"].sum() < 24
        assert hist_1d.daily_counts["06-22"].sum() < 24
