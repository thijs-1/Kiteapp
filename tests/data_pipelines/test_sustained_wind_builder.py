"""Tests for sustained wind builder."""
import numpy as np
import pytest

from data_pipelines.services.sustained_wind_builder import SustainedWindBuilder
from data_pipelines.config import WIND_BINS


class TestSustainedWindBuilder:
    """Tests for SustainedWindBuilder."""

    def test_compute_rolling_min_max_basic(self):
        """Test basic rolling min-max computation."""
        builder = SustainedWindBuilder(sustained_hours=2, filter_daylight=False)

        # Wind speeds: [10, 15, 20, 12, 8]
        # Rolling min (window=2): [nan, 10, 15, 12, 8]
        # Max of rolling mins: 15
        wind_strength = np.array([10, 15, 20, 12, 8], dtype=np.float32)

        result = builder._compute_rolling_min_max(wind_strength, window_size=2)
        assert result == 15.0

    def test_compute_rolling_min_max_sustained_high(self):
        """Test that sustained high wind is captured."""
        builder = SustainedWindBuilder(sustained_hours=2, filter_daylight=False)

        # Wind speeds: [5, 5, 25, 25, 25, 5, 5]
        # Rolling min (window=2): [nan, 5, 5, 25, 25, 5, 5]
        # Max of rolling mins: 25 (sustained for 3 hours)
        wind_strength = np.array([5, 5, 25, 25, 25, 5, 5], dtype=np.float32)

        result = builder._compute_rolling_min_max(wind_strength, window_size=2)
        assert result == 25.0

    def test_compute_rolling_min_max_spike_not_sustained(self):
        """Test that a spike that's not sustained is not captured."""
        builder = SustainedWindBuilder(sustained_hours=2, filter_daylight=False)

        # Wind speeds: [10, 30, 10, 10]
        # Rolling min (window=2): [nan, 10, 10, 10]
        # Max of rolling mins: 10 (the 30 spike is not sustained)
        wind_strength = np.array([10, 30, 10, 10], dtype=np.float32)

        result = builder._compute_rolling_min_max(wind_strength, window_size=2)
        assert result == 10.0

    def test_compute_rolling_min_max_insufficient_data(self):
        """Test with insufficient data for window."""
        builder = SustainedWindBuilder(sustained_hours=2, filter_daylight=False)

        # Only 1 data point, window requires 2
        wind_strength = np.array([15], dtype=np.float32)

        result = builder._compute_rolling_min_max(wind_strength, window_size=2)
        assert result == 0.0

    def test_compute_rolling_min_max_3_hour_window(self):
        """Test with 3-hour sustained window."""
        builder = SustainedWindBuilder(sustained_hours=3, filter_daylight=False)

        # Wind speeds: [5, 20, 20, 20, 5]
        # Rolling min (window=3): [nan, nan, 5, 20, 5]
        # Max of rolling mins: 20
        wind_strength = np.array([5, 20, 20, 20, 5], dtype=np.float32)

        result = builder._compute_rolling_min_max(wind_strength, window_size=3)
        assert result == 20.0

    def test_build_histogram_single_day(self):
        """Test building histogram for a single day."""
        builder = SustainedWindBuilder(sustained_hours=2, filter_daylight=False)

        # Create 24 hours of data for one day with sustained 15 knots
        timestamps = np.array([
            np.datetime64("2024-06-21") + np.timedelta64(h, 'h')
            for h in range(24)
        ])
        wind_strength = np.ones(24, dtype=np.float32) * 15

        result = builder.build_daily_sustained_wind(
            "test_spot", timestamps, wind_strength
        )

        assert result.spot_id == "test_spot"
        assert result.sustained_hours == 2
        assert result.bins == WIND_BINS
        assert "06-21" in result.daily_counts

        # 15 knots falls in bin [12.5, 15) which is index 5, or bin [15, 17.5) which is index 6
        # Bins: [0, 2.5, 5, 7.5, 10, 12.5, 15, 17.5, ...]
        # 15.0 falls in bin index 6 (15 <= x < 17.5)
        counts = result.daily_counts["06-21"]
        assert counts.sum() == 1  # One calendar day
        assert counts[6] == 1  # 15 knots is in bin [15, 17.5)

    def test_build_histogram_multi_year(self):
        """Test that multi-year data creates histogram counts (not averages)."""
        builder = SustainedWindBuilder(sustained_hours=2, filter_daylight=False)

        # Create data for same day across two years
        # Year 1: June 21 with sustained 15 knots
        timestamps_year1 = np.array([
            np.datetime64("2023-06-21") + np.timedelta64(h, 'h')
            for h in range(24)
        ])
        wind_year1 = np.ones(24, dtype=np.float32) * 15

        # Year 2: June 21 with sustained 25 knots
        timestamps_year2 = np.array([
            np.datetime64("2024-06-21") + np.timedelta64(h, 'h')
            for h in range(24)
        ])
        wind_year2 = np.ones(24, dtype=np.float32) * 25

        # Combine both years
        timestamps = np.concatenate([timestamps_year1, timestamps_year2])
        wind_strength = np.concatenate([wind_year1, wind_year2])

        result = builder.build_daily_sustained_wind(
            "test_spot", timestamps, wind_strength
        )

        assert "06-21" in result.daily_counts
        counts = result.daily_counts["06-21"]

        # Should have 2 total days counted
        assert counts.sum() == 2

        # 15 knots in bin [15, 17.5) = index 6
        # 25 knots in bin [25, 27.5) = index 10
        assert counts[6] == 1
        assert counts[10] == 1

    def test_percentage_calculation(self):
        """Test that histogram allows percentage calculation."""
        builder = SustainedWindBuilder(sustained_hours=2, filter_daylight=False)

        # Create 10 years of data for June 21
        # 7 years with 20 knots sustained, 3 years with 5 knots sustained
        timestamps = []
        wind_strength = []

        for year in range(2015, 2025):
            year_ts = np.array([
                np.datetime64(f"{year}-06-21") + np.timedelta64(h, 'h')
                for h in range(24)
            ])
            timestamps.append(year_ts)

            if year < 2022:  # 7 years with 20 knots
                wind_strength.append(np.ones(24, dtype=np.float32) * 20)
            else:  # 3 years with 5 knots
                wind_strength.append(np.ones(24, dtype=np.float32) * 5)

        timestamps = np.concatenate(timestamps)
        wind_strength = np.concatenate(wind_strength)

        result = builder.build_daily_sustained_wind(
            "test_spot", timestamps, wind_strength
        )

        counts = result.daily_counts["06-21"]
        total_days = counts.sum()

        # Calculate percentage of days with sustained wind >= 15 knots
        # Bins: [0, 2.5, 5, 7.5, 10, 12.5, 15, 17.5, 20, 22.5, ...]
        # Index 6 is [15, 17.5), we want sum from index 6 onwards
        days_above_15 = counts[6:].sum()
        percentage = (days_above_15 / total_days) * 100

        assert total_days == 10
        assert days_above_15 == 7
        assert percentage == 70.0

    def test_to_dict(self):
        """Test that to_dict returns serializable data."""
        builder = SustainedWindBuilder(sustained_hours=2, filter_daylight=False)

        timestamps = np.array([
            np.datetime64("2024-06-21") + np.timedelta64(h, 'h')
            for h in range(24)
        ])
        wind_strength = np.ones(24, dtype=np.float32) * 15

        result = builder.build_daily_sustained_wind(
            "test_spot", timestamps, wind_strength
        )

        data = result.to_dict()
        assert data["spot_id"] == "test_spot"
        assert data["sustained_hours"] == 2
        assert data["bins"] == WIND_BINS
        assert "06-21" in data["daily_counts"]
        assert isinstance(data["daily_counts"]["06-21"], list)

    def test_empty_data(self):
        """Test handling of empty data."""
        builder = SustainedWindBuilder(sustained_hours=2, filter_daylight=False)

        timestamps = np.array([], dtype='datetime64[ns]')
        wind_strength = np.array([], dtype=np.float32)

        result = builder.build_daily_sustained_wind(
            "test_spot", timestamps, wind_strength
        )

        assert result.spot_id == "test_spot"
        assert result.daily_counts == {}

    def test_daylight_filter_enabled_by_default(self):
        """Test that daylight filtering uses config default."""
        builder = SustainedWindBuilder(sustained_hours=2)
        from data_pipelines.config import FILTER_DAYLIGHT_HOURS
        assert builder.filter_daylight == FILTER_DAYLIGHT_HOURS

    def test_bins_match_config(self):
        """Test that default bins match WIND_BINS config."""
        builder = SustainedWindBuilder(sustained_hours=2, filter_daylight=False)
        assert builder.bins == WIND_BINS
