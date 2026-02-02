"""Tests for sustained wind builder."""
import numpy as np
import pytest

from data_pipelines.services.sustained_wind_builder import SustainedWindBuilder


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

    def test_build_daily_sustained_wind_basic(self):
        """Test building daily sustained wind data."""
        builder = SustainedWindBuilder(sustained_hours=2, filter_daylight=False)

        # Create 24 hours of data for one day
        timestamps = np.array([
            np.datetime64("2024-06-21") + np.timedelta64(h, 'h')
            for h in range(24)
        ])

        # Wind with sustained high in middle of day
        wind_strength = np.concatenate([
            np.ones(8, dtype=np.float32) * 10,    # 10 knots for 8 hours
            np.ones(8, dtype=np.float32) * 25,    # 25 knots for 8 hours (sustained)
            np.ones(8, dtype=np.float32) * 10,    # 10 knots for 8 hours
        ])

        result = builder.build_daily_sustained_wind(
            "test_spot", timestamps, wind_strength
        )

        assert result.spot_id == "test_spot"
        assert result.sustained_hours == 2
        assert "06-21" in result.daily_max_sustained
        # Max sustained should be 25 (sustained for 8 hours)
        assert result.daily_max_sustained["06-21"] == 25.0

    def test_build_daily_sustained_wind_multiple_days(self):
        """Test building sustained wind for multiple days."""
        builder = SustainedWindBuilder(sustained_hours=2, filter_daylight=False)

        # Create 48 hours of data for two days
        timestamps = np.array([
            np.datetime64("2024-06-21") + np.timedelta64(h, 'h')
            for h in range(48)
        ])

        # Day 1: max sustained 15 knots, Day 2: max sustained 20 knots
        wind_strength = np.concatenate([
            np.ones(24, dtype=np.float32) * 15,  # Day 1: constant 15
            np.ones(24, dtype=np.float32) * 20,  # Day 2: constant 20
        ])

        result = builder.build_daily_sustained_wind(
            "test_spot", timestamps, wind_strength
        )

        assert "06-21" in result.daily_max_sustained
        assert "06-22" in result.daily_max_sustained
        assert result.daily_max_sustained["06-21"] == 15.0
        assert result.daily_max_sustained["06-22"] == 20.0

    def test_build_daily_sustained_wind_variable_conditions(self):
        """Test with realistic variable wind conditions."""
        builder = SustainedWindBuilder(sustained_hours=2, filter_daylight=False)

        # Create 24 hours: gusty start, sustained middle, gusty end
        timestamps = np.array([
            np.datetime64("2024-06-21") + np.timedelta64(h, 'h')
            for h in range(24)
        ])

        # Pattern: [5, 15, 8, 12, 10, 18, 18, 18, 18, 18, 18, 18, 10, 5, ...]
        wind_strength = np.array([
            5, 15, 8, 12, 10,           # Variable morning (5 hours)
            18, 18, 18, 18, 18, 18, 18, # Sustained afternoon (7 hours at 18)
            10, 5, 8, 12, 6, 4, 5, 6,   # Variable evening (8 hours)
            3, 4, 2, 3,                 # Night (4 hours)
        ], dtype=np.float32)

        result = builder.build_daily_sustained_wind(
            "test_spot", timestamps, wind_strength
        )

        # Max sustained should be 18 (sustained for 7 hours)
        assert result.daily_max_sustained["06-21"] == 18.0

    def test_build_daily_sustained_wind_multi_year_averaging(self):
        """Test that multi-year data is averaged correctly by day-of-year."""
        builder = SustainedWindBuilder(sustained_hours=2, filter_daylight=False)

        # Create data for same day across two years
        # Year 1: June 21 with sustained 20 knots
        timestamps_year1 = np.array([
            np.datetime64("2023-06-21") + np.timedelta64(h, 'h')
            for h in range(24)
        ])
        wind_year1 = np.ones(24, dtype=np.float32) * 20

        # Year 2: June 21 with sustained 30 knots
        timestamps_year2 = np.array([
            np.datetime64("2024-06-21") + np.timedelta64(h, 'h')
            for h in range(24)
        ])
        wind_year2 = np.ones(24, dtype=np.float32) * 30

        # Combine both years
        timestamps = np.concatenate([timestamps_year1, timestamps_year2])
        wind_strength = np.concatenate([wind_year1, wind_year2])

        result = builder.build_daily_sustained_wind(
            "test_spot", timestamps, wind_strength
        )

        # Should average: (20 + 30) / 2 = 25
        assert "06-21" in result.daily_max_sustained
        assert result.daily_max_sustained["06-21"] == 25.0

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
        assert "06-21" in data["daily_max_sustained"]
        assert isinstance(data["daily_max_sustained"]["06-21"], float)

    def test_empty_data_after_filter(self):
        """Test handling of empty data."""
        builder = SustainedWindBuilder(sustained_hours=2, filter_daylight=False)

        timestamps = np.array([], dtype='datetime64[ns]')
        wind_strength = np.array([], dtype=np.float32)

        result = builder.build_daily_sustained_wind(
            "test_spot", timestamps, wind_strength
        )

        assert result.spot_id == "test_spot"
        assert result.daily_max_sustained == {}

    def test_daylight_filter_enabled_by_default(self):
        """Test that daylight filtering uses config default."""
        # The builder should use FILTER_DAYLIGHT_HOURS from config by default
        builder = SustainedWindBuilder(sustained_hours=2)
        # filter_daylight should match the config value
        from data_pipelines.config import FILTER_DAYLIGHT_HOURS
        assert builder.filter_daylight == FILTER_DAYLIGHT_HOURS
