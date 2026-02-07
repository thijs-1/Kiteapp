"""Tests for the daylight service."""
from datetime import datetime, timezone
import numpy as np
import pytest

from data_pipelines.services.daylight_service import DaylightService


class TestDaylightService:
    """Tests for DaylightService."""

    def test_initialization_with_filter_enabled(self):
        """Test initialization with filtering enabled."""
        service = DaylightService(filter_enabled=True)
        assert service.filter_enabled is True

    def test_initialization_with_filter_disabled(self):
        """Test initialization with filtering disabled."""
        service = DaylightService(filter_enabled=False)
        assert service.filter_enabled is False

    def test_get_sunrise_sunset_mid_latitude_summer(self):
        """Test sunrise/sunset for mid-latitude location in summer."""
        service = DaylightService(filter_enabled=True, depression_angle=0)

        # Amsterdam, Netherlands (52.37°N) on June 21 (summer solstice)
        latitude = 52.37
        longitude = 4.89
        date = datetime(2024, 6, 21)

        sunrise, sunset = service.get_sunrise_sunset_utc(latitude, longitude, date)

        assert sunrise is not None
        assert sunset is not None
        # Summer in Amsterdam: sunrise around 3:15-3:30 UTC, sunset around 20:00-20:30 UTC
        assert sunrise.hour < 5
        assert sunset.hour > 19

    def test_get_sunrise_sunset_mid_latitude_winter(self):
        """Test sunrise/sunset for mid-latitude location in winter."""
        service = DaylightService(filter_enabled=True, depression_angle=0)

        # Amsterdam, Netherlands (52.37°N) on December 21 (winter solstice)
        latitude = 52.37
        longitude = 4.89
        date = datetime(2024, 12, 21)

        sunrise, sunset = service.get_sunrise_sunset_utc(latitude, longitude, date)

        assert sunrise is not None
        assert sunset is not None
        # Winter in Amsterdam: sunrise around 7:30-8:00 UTC, sunset around 15:30-16:00 UTC
        assert sunrise.hour >= 7
        assert sunset.hour < 17

    def test_get_sunrise_sunset_equator(self):
        """Test sunrise/sunset at equator (consistent ~12h daylight)."""
        service = DaylightService(filter_enabled=True, depression_angle=0)

        # Quito, Ecuador (0.18°S) - near equator, closer to UTC
        latitude = -0.18
        longitude = -78.47
        date = datetime(2024, 3, 20)  # Equinox

        sunrise, sunset = service.get_sunrise_sunset_utc(latitude, longitude, date)

        assert sunrise is not None
        assert sunset is not None
        # At equator, daylight should be roughly 12 hours
        daylight_hours = (sunset - sunrise).total_seconds() / 3600
        assert 11 < daylight_hours < 13

    def test_get_sunrise_sunset_with_civil_twilight(self):
        """Test sunrise/sunset with civil twilight (6 degree depression)."""
        service = DaylightService(filter_enabled=True, depression_angle=6)

        latitude = 52.37
        longitude = 4.89
        date = datetime(2024, 6, 21)

        sunrise, sunset = service.get_sunrise_sunset_utc(latitude, longitude, date)

        # With civil twilight, daylight period should be longer
        assert sunrise is not None
        assert sunset is not None

        # Compare with geometric sunrise/sunset
        service_geo = DaylightService(filter_enabled=True, depression_angle=0)
        sunrise_geo, sunset_geo = service_geo.get_sunrise_sunset_utc(latitude, longitude, date)

        # Civil twilight should start earlier (dawn) and end later (dusk)
        assert sunrise < sunrise_geo
        assert sunset > sunset_geo

    def test_is_daylight_during_day(self):
        """Test is_daylight returns True during daytime."""
        service = DaylightService(filter_enabled=True, depression_angle=0)

        # Amsterdam at noon UTC on June 21
        latitude = 52.37
        longitude = 4.89
        timestamp = datetime(2024, 6, 21, 12, 0, tzinfo=timezone.utc)

        assert service.is_daylight(latitude, longitude, timestamp) is True

    def test_is_daylight_during_night(self):
        """Test is_daylight returns False during nighttime."""
        service = DaylightService(filter_enabled=True, depression_angle=0)

        # Amsterdam at midnight UTC on June 21 (still night at 00:00 UTC)
        latitude = 52.37
        longitude = 4.89
        timestamp = datetime(2024, 6, 21, 0, 0, tzinfo=timezone.utc)

        assert service.is_daylight(latitude, longitude, timestamp) is False

    def test_is_daylight_filter_disabled(self):
        """Test is_daylight always returns True when filter is disabled."""
        service = DaylightService(filter_enabled=False)

        # Should return True even at midnight
        latitude = 52.37
        longitude = 4.89
        timestamp = datetime(2024, 6, 21, 0, 0, tzinfo=timezone.utc)

        assert service.is_daylight(latitude, longitude, timestamp) is True

    def test_create_daylight_mask_filters_nighttime(self):
        """Test create_daylight_mask properly filters nighttime hours."""
        service = DaylightService(filter_enabled=True, depression_angle=0)

        # Amsterdam location
        latitude = 52.37
        longitude = 4.89

        # Create hourly timestamps for one day (June 21, 2024)
        base = datetime(2024, 6, 21, 0, 0)
        timestamps = np.array([
            np.datetime64(f"2024-06-21T{h:02d}:00:00") for h in range(24)
        ])

        mask = service.create_daylight_mask(latitude, longitude, timestamps)

        # Should have some True and some False values
        assert mask.sum() > 0
        assert mask.sum() < len(mask)

        # Midday should be True (index 12 = noon)
        assert mask[12] == True

        # Early morning (00:00-03:00 UTC) should be False for Amsterdam
        assert mask[0] == False
        assert mask[1] == False
        assert mask[2] == False

    def test_create_daylight_mask_filter_disabled(self):
        """Test create_daylight_mask returns all True when filter disabled."""
        service = DaylightService(filter_enabled=False)

        latitude = 52.37
        longitude = 4.89
        timestamps = np.array([
            np.datetime64(f"2024-06-21T{h:02d}:00:00") for h in range(24)
        ])

        mask = service.create_daylight_mask(latitude, longitude, timestamps)

        # All values should be True
        assert mask.all()

    def test_get_daylight_stats(self):
        """Test get_daylight_stats returns correct statistics."""
        service = DaylightService(filter_enabled=True, depression_angle=0)

        latitude = 52.37
        longitude = 4.89
        timestamps = np.array([
            np.datetime64(f"2024-06-21T{h:02d}:00:00") for h in range(24)
        ])

        stats = service.get_daylight_stats(latitude, longitude, timestamps)

        assert "total_hours" in stats
        assert "daylight_hours" in stats
        assert "filtered_hours" in stats
        assert "daylight_percentage" in stats

        assert stats["total_hours"] == 24
        assert stats["daylight_hours"] + stats["filtered_hours"] == 24
        assert 0 < stats["daylight_percentage"] < 100

    def test_cache_improves_performance(self):
        """Test that caching works (same result for repeated calls)."""
        service = DaylightService(filter_enabled=True)

        latitude = 52.37
        longitude = 4.89
        date = datetime(2024, 6, 21)

        # First call
        result1 = service.get_sunrise_sunset_utc(latitude, longitude, date)

        # Second call (should use cache)
        result2 = service.get_sunrise_sunset_utc(latitude, longitude, date)

        assert result1 == result2

    def test_clear_cache(self):
        """Test that cache can be cleared."""
        service = DaylightService(filter_enabled=True)

        latitude = 52.37
        longitude = 4.89
        date = datetime(2024, 6, 21)

        # Populate cache
        service.get_sunrise_sunset_utc(latitude, longitude, date)
        assert len(service._cache) > 0

        # Clear cache
        service.clear_cache()
        assert len(service._cache) == 0


class TestDaylightServiceEdgeCases:
    """Tests for edge cases in DaylightService."""

    def test_southern_hemisphere_summer(self):
        """Test that seasons are correctly handled in southern hemisphere."""
        service = DaylightService(filter_enabled=True, depression_angle=0)

        # Cape Town, South Africa (-33.92°S) in December (southern summer)
        latitude = -33.92
        longitude = 18.42
        date = datetime(2024, 12, 21)

        sunrise, sunset = service.get_sunrise_sunset_utc(latitude, longitude, date)

        assert sunrise is not None
        assert sunset is not None
        # Summer in Cape Town: long days
        daylight_hours = (sunset - sunrise).total_seconds() / 3600
        assert daylight_hours > 13

    def test_longitude_affects_utc_times(self):
        """Test that different longitudes produce different UTC times."""
        service = DaylightService(filter_enabled=True, depression_angle=0)

        date = datetime(2024, 6, 21)

        # Same latitude, different longitudes
        # London (0°) - near prime meridian
        sunrise_london, _ = service.get_sunrise_sunset_utc(51.51, -0.13, date)
        # Tokyo (139°E) - far east
        sunrise_tokyo, _ = service.get_sunrise_sunset_utc(35.68, 139.69, date)

        # Tokyo is ~9 hours ahead of London in local time
        # So Tokyo sunrise in UTC should be earlier than London sunrise in UTC
        # (Tokyo sees the sun first as Earth rotates)
        assert sunrise_tokyo.hour != sunrise_london.hour  # Different UTC hours

    def test_handles_year_boundary(self):
        """Test that year boundaries are handled correctly."""
        service = DaylightService(filter_enabled=True)

        latitude = 52.37
        longitude = 4.89

        # December 31
        dec31 = datetime(2024, 12, 31)
        sunrise_dec, sunset_dec = service.get_sunrise_sunset_utc(latitude, longitude, dec31)

        # January 1
        jan1 = datetime(2025, 1, 1)
        sunrise_jan, sunset_jan = service.get_sunrise_sunset_utc(latitude, longitude, jan1)

        # Both should return valid results
        assert sunrise_dec is not None
        assert sunset_jan is not None

        # Both sunrise times should be similar hours (around 7:30-8:00 UTC in winter)
        # The hour should be the same or differ by at most 1
        assert abs(sunrise_jan.hour - sunrise_dec.hour) <= 1

    def test_multi_year_timestamps(self):
        """Test daylight mask with timestamps spanning multiple years."""
        service = DaylightService(filter_enabled=True)

        latitude = 52.37
        longitude = 4.89

        # Create timestamps spanning two years
        timestamps = np.array([
            np.datetime64("2024-12-31T12:00:00"),
            np.datetime64("2025-01-01T12:00:00"),
        ])

        mask = service.create_daylight_mask(latitude, longitude, timestamps)

        # Both noon timestamps should be during daylight
        assert mask[0] == True
        assert mask[1] == True

    def test_eastern_longitude_dawn_crosses_utc_midnight(self):
        """Test that daylight filtering works when dawn falls before UTC midnight.

        For eastern longitudes (e.g. Sri Lanka east coast at ~82°E), civil dawn
        in UTC can fall just before midnight. The astral library places this dawn
        at the END of the UTC date (23:53) instead of the beginning, making
        dawn > dusk. The filter must handle this correctly.
        """
        service = DaylightService(filter_enabled=True, depression_angle=6)

        # Arugam Bay, Sri Lanka (6.84°N, 81.83°E) in May
        # Dawn ~23:53 UTC (05:23 local), Dusk ~13:04 UTC (18:34 local)
        latitude = 6.84
        longitude = 81.83

        # Hourly timestamps for one UTC day in May
        timestamps = np.array([
            np.datetime64(f"2024-05-15T{h:02d}:00:00") for h in range(24)
        ])

        mask = service.create_daylight_mask(latitude, longitude, timestamps)

        # Should have ~13-14 daylight hours, NOT 0
        assert mask.sum() > 10, (
            f"Expected >10 daylight hours for Sri Lanka in May, got {mask.sum()}. "
            f"Dawn/dusk UTC midnight crossing likely not handled."
        )

        # Morning hours (00:00-12:00 UTC = 05:30-17:30 local) should be daylight
        assert mask[6] == True   # 06:00 UTC = 11:30 local
        assert mask[12] == True  # 12:00 UTC = 17:30 local

        # Late afternoon/night (15:00+ UTC = 20:30+ local) should be dark
        assert mask[15] == False  # 15:00 UTC = 20:30 local
        assert mask[20] == False  # 20:00 UTC = 01:30 local next day

    def test_western_longitude_dusk_crosses_utc_midnight(self):
        """Test that daylight filtering works for western hemisphere locations.

        For western longitudes (e.g. Hawaii at ~-155°), dusk in UTC can fall
        just after midnight (early hours), creating the same dawn > dusk
        inversion but from the dusk side.
        """
        service = DaylightService(filter_enabled=True, depression_angle=6)

        # Hawaii (~20°N, -155°W) in May
        # Dawn ~15:16 UTC (05:16 local), Dusk ~05:17 UTC (19:17 local prev day)
        latitude = 20.0
        longitude = -155.0

        timestamps = np.array([
            np.datetime64(f"2024-05-25T{h:02d}:00:00") for h in range(24)
        ])

        mask = service.create_daylight_mask(latitude, longitude, timestamps)

        # Should have ~13-14 daylight hours, NOT 0
        assert mask.sum() > 10, (
            f"Expected >10 daylight hours for Hawaii in May, got {mask.sum()}. "
            f"Dawn/dusk UTC midnight crossing likely not handled."
        )

        # Early UTC hours (00:00-05:00 = 14:00-19:00 local prev day) should be daylight
        assert mask[0] == True   # 00:00 UTC = 14:00 HST
        assert mask[4] == True   # 04:00 UTC = 18:00 HST

        # Mid UTC hours (07:00-14:00 = 21:00-04:00 local) should be dark
        assert mask[8] == False   # 08:00 UTC = 22:00 HST
        assert mask[14] == False  # 14:00 UTC = 04:00 HST

        # Late UTC hours (16:00-23:00 = 06:00-13:00 local) should be daylight
        assert mask[16] == True  # 16:00 UTC = 06:00 HST
        assert mask[23] == True  # 23:00 UTC = 13:00 HST

    def test_is_daylight_eastern_longitude_midnight_crossing(self):
        """Test is_daylight works for locations where dawn crosses UTC midnight."""
        service = DaylightService(filter_enabled=True, depression_angle=6)

        latitude = 6.84   # Arugam Bay
        longitude = 81.83

        # 06:00 UTC = 11:30 local -> definitely daylight
        ts_day = datetime(2024, 5, 15, 6, 0, tzinfo=timezone.utc)
        assert service.is_daylight(latitude, longitude, ts_day) is True

        # 18:00 UTC = 23:30 local -> definitely night
        ts_night = datetime(2024, 5, 15, 18, 0, tzinfo=timezone.utc)
        assert service.is_daylight(latitude, longitude, ts_night) is False
