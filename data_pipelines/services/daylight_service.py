"""Service for calculating daylight hours at a given location."""
from datetime import datetime, timezone, timedelta
from typing import Optional, Tuple
import numpy as np
import pandas as pd
from astral import Observer
from astral.sun import sun

from data_pipelines.config import (
    FILTER_DAYLIGHT_HOURS,
    DAYLIGHT_DEPRESSION_ANGLE,
)


class DaylightService:
    """
    Service for calculating sunrise/sunset times and filtering timestamps by daylight.

    Uses the astral library to compute solar position based on geographic coordinates.
    ERA5 timestamps are in UTC, so sunrise/sunset times are also computed in UTC.
    """

    def __init__(
        self,
        filter_enabled: bool = FILTER_DAYLIGHT_HOURS,
        depression_angle: float = DAYLIGHT_DEPRESSION_ANGLE,
    ):
        """
        Initialize the daylight service.

        Args:
            filter_enabled: Whether to apply daylight filtering
            depression_angle: Sun depression angle for twilight definition.
                             0 = geometric sunrise/sunset (sun center at horizon)
                             6 = civil twilight (enough light for outdoor activities)
                            12 = nautical twilight
                            18 = astronomical twilight
        """
        self.filter_enabled = filter_enabled
        self.depression_angle = depression_angle

        # Cache for sunrise/sunset times: (lat, lon, date) -> (sunrise_utc, sunset_utc)
        self._cache: dict = {}

    def get_sunrise_sunset_utc(
        self,
        latitude: float,
        longitude: float,
        date: datetime,
    ) -> Tuple[Optional[datetime], Optional[datetime]]:
        """
        Calculate sunrise and sunset times in UTC for a given location and date.

        Args:
            latitude: Latitude in degrees (-90 to 90)
            longitude: Longitude in degrees (-180 to 180)
            date: The date to calculate for (only date part is used)

        Returns:
            Tuple of (sunrise_utc, sunset_utc) as timezone-aware datetimes.
            Returns (None, None) for polar day (24h daylight) or polar night (24h darkness).
        """
        # Round coordinates to reduce cache size
        lat_key = round(latitude, 2)
        lon_key = round(longitude, 2)
        date_key = date.date() if isinstance(date, datetime) else date

        cache_key = (lat_key, lon_key, date_key)
        if cache_key in self._cache:
            return self._cache[cache_key]

        observer = Observer(latitude=latitude, longitude=longitude)

        try:
            sun_times = sun(
                observer,
                date=date_key,
                tzinfo=timezone.utc,
                dawn_dusk_depression=self.depression_angle,
            )

            # Use dawn/dusk if depression angle is set, otherwise sunrise/sunset
            if self.depression_angle > 0:
                sunrise_utc = sun_times["dawn"]
                sunset_utc = sun_times["dusk"]
            else:
                sunrise_utc = sun_times["sunrise"]
                sunset_utc = sun_times["sunset"]

            result = (sunrise_utc, sunset_utc)

        except ValueError:
            # Polar day or polar night - sun doesn't rise/set
            # Check if we're in polar day (sun always up) or polar night (sun always down)
            try:
                noon = sun(observer, date=date_key, tzinfo=timezone.utc)["noon"]
                # If we can calculate noon, check sun elevation at noon
                # For simplicity, assume polar day if latitude and date suggest summer
                # and polar night if winter
                day_of_year = date_key.timetuple().tm_yday
                is_northern_summer = 80 < day_of_year < 265  # Roughly March-September
                is_polar_day = (latitude > 60 and is_northern_summer) or \
                               (latitude < -60 and not is_northern_summer)

                if is_polar_day:
                    # 24h daylight - return full day span
                    result = (
                        datetime.combine(date_key, datetime.min.time(), tzinfo=timezone.utc),
                        datetime.combine(date_key, datetime.max.time().replace(microsecond=0), tzinfo=timezone.utc),
                    )
                else:
                    # 24h darkness - return None to indicate no valid daylight
                    result = (None, None)
            except Exception:
                result = (None, None)

        self._cache[cache_key] = result
        return result

    def is_daylight(
        self,
        latitude: float,
        longitude: float,
        timestamp_utc: datetime,
    ) -> bool:
        """
        Check if a given UTC timestamp is during daylight hours at the location.

        Args:
            latitude: Latitude in degrees
            longitude: Longitude in degrees
            timestamp_utc: UTC timestamp to check

        Returns:
            True if the timestamp is during daylight hours
        """
        if not self.filter_enabled:
            return True

        sunrise, sunset = self.get_sunrise_sunset_utc(latitude, longitude, timestamp_utc)

        if sunrise is None or sunset is None:
            # Polar night - no daylight
            return False

        # Make timestamp timezone-aware if needed
        if timestamp_utc.tzinfo is None:
            timestamp_utc = timestamp_utc.replace(tzinfo=timezone.utc)

        if sunrise <= sunset:
            return sunrise <= timestamp_utc <= sunset
        else:
            # Daylight spans UTC midnight (e.g. eastern longitudes where dawn
            # in UTC falls before midnight of the requested date)
            return timestamp_utc >= sunrise or timestamp_utc <= sunset

    def create_daylight_mask(
        self,
        latitude: float,
        longitude: float,
        timestamps: np.ndarray,
    ) -> np.ndarray:
        """
        Create a boolean mask indicating which timestamps fall within daylight hours.

        This is optimized for batch processing of many timestamps.

        Args:
            latitude: Latitude in degrees
            longitude: Longitude in degrees
            timestamps: Array of numpy datetime64 timestamps (UTC)

        Returns:
            Boolean array where True indicates daylight hours
        """
        if not self.filter_enabled:
            return np.ones(len(timestamps), dtype=bool)

        # Convert numpy datetime64 to pandas for easier date handling
        dates = pd.to_datetime(timestamps)

        # Get unique dates and pre-compute sunrise/sunset for each
        unique_dates = dates.normalize().unique()

        # Build lookup for each unique date
        sunrise_lookup = {}
        sunset_lookup = {}

        for date in unique_dates:
            date_dt = date.to_pydatetime()
            sunrise, sunset = self.get_sunrise_sunset_utc(latitude, longitude, date_dt)
            if sunrise is not None and sunset is not None:
                # Convert to numpy datetime64 for comparison
                sunrise_lookup[date] = np.datetime64(sunrise.replace(tzinfo=None))
                sunset_lookup[date] = np.datetime64(sunset.replace(tzinfo=None))
            else:
                sunrise_lookup[date] = None
                sunset_lookup[date] = None

        # Create mask for each timestamp
        mask = np.zeros(len(timestamps), dtype=bool)

        for i, (ts, date) in enumerate(zip(timestamps, dates.normalize())):
            sunrise = sunrise_lookup.get(date)
            sunset = sunset_lookup.get(date)

            if sunrise is not None and sunset is not None:
                if sunrise <= sunset:
                    mask[i] = (ts >= sunrise) and (ts <= sunset)
                else:
                    # Daylight spans UTC midnight
                    mask[i] = (ts >= sunrise) or (ts <= sunset)

        return mask

    def get_daylight_stats(
        self,
        latitude: float,
        longitude: float,
        timestamps: np.ndarray,
    ) -> dict:
        """
        Get statistics about daylight filtering for a spot.

        Args:
            latitude: Latitude in degrees
            longitude: Longitude in degrees
            timestamps: Array of numpy datetime64 timestamps (UTC)

        Returns:
            Dict with filtering statistics
        """
        mask = self.create_daylight_mask(latitude, longitude, timestamps)

        return {
            "total_hours": len(timestamps),
            "daylight_hours": int(np.sum(mask)),
            "filtered_hours": int(np.sum(~mask)),
            "daylight_percentage": float(np.mean(mask) * 100),
        }

    def clear_cache(self) -> None:
        """Clear the sunrise/sunset cache."""
        self._cache.clear()
