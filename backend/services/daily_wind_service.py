"""Service for computing daily wind profiles from timeseries data."""
from datetime import datetime, timezone, timedelta
from typing import Optional, List
import numpy as np
import pandas as pd
from astral import Observer
from astral.sun import sun

from backend.data.spot_repository import SpotRepository
from backend.data.timeseries_repository import TimeseriesRepository
from backend.schemas.daily_wind import DayProfile, DailyWindProfileResponse

DAYLIGHT_DEPRESSION_ANGLE = 6.0  # Civil twilight


class DailyWindService:
    """Service for daily wind profile operations."""

    def __init__(
        self,
        spot_repo: SpotRepository = None,
        timeseries_repo: TimeseriesRepository = None,
    ):
        self.spot_repo = spot_repo or SpotRepository()
        self.timeseries_repo = timeseries_repo or TimeseriesRepository()

    def _get_dawn_dusk_utc(
        self, latitude: float, longitude: float, date,
    ):
        """Get dawn/dusk times in UTC for a location and date."""
        observer = Observer(latitude=latitude, longitude=longitude)
        try:
            sun_times = sun(
                observer,
                date=date,
                tzinfo=timezone.utc,
                dawn_dusk_depression=DAYLIGHT_DEPRESSION_ANGLE,
            )
            return sun_times["dawn"], sun_times["dusk"]
        except ValueError:
            # Polar day/night
            day_of_year = date.timetuple().tm_yday
            is_northern_summer = 80 < day_of_year < 265
            is_polar_day = (latitude > 60 and is_northern_summer) or \
                           (latitude < -60 and not is_northern_summer)
            if is_polar_day:
                return (
                    datetime.combine(date, datetime.min.time(), tzinfo=timezone.utc),
                    datetime.combine(date, datetime.max.time().replace(microsecond=0), tzinfo=timezone.utc),
                )
            return None, None

    def get_daily_wind_profiles(
        self,
        spot_id: str,
        start_date: str = "01-01",
        end_date: str = "12-31",
    ) -> Optional[DailyWindProfileResponse]:
        """
        Get daily wind profiles (dawn-to-dusk) for a spot.

        Args:
            spot_id: Spot ID
            start_date: Start date (MM-DD)
            end_date: End date (MM-DD)

        Returns:
            DailyWindProfileResponse with individual day profiles, or None if no data
        """
        # Load spot metadata for lat/lon
        spot = self.spot_repo.get_spot_by_id(spot_id)
        if spot is None:
            return None

        latitude = spot["latitude"]
        longitude = spot["longitude"]

        # Load timeseries
        ts_data = self.timeseries_repo.load_timeseries(spot_id)
        if ts_data is None:
            return None

        timestamps = ts_data["time"]
        strength = ts_data["strength"]

        if len(timestamps) == 0:
            return DailyWindProfileResponse(
                spot_id=spot_id,
                timezone_offset_hours=longitude / 15.0,
                profiles=[],
            )

        # Compute local time offset (solar time)
        tz_offset_hours = longitude / 15.0
        tz_offset = timedelta(hours=tz_offset_hours)

        # Convert to pandas for grouping
        utc_times = pd.to_datetime(timestamps)
        local_times = utc_times + tz_offset

        df = pd.DataFrame({
            "utc_time": utc_times,
            "local_time": local_times,
            "local_date": local_times.date,
            "strength": strength,
        })

        # Filter by day-of-year (MM-DD range)
        df["mm_dd"] = local_times.strftime("%m-%d")
        if start_date <= end_date:
            df = df[(df["mm_dd"] >= start_date) & (df["mm_dd"] <= end_date)]
        else:
            # Wrap-around (e.g., Nov to Feb)
            df = df[(df["mm_dd"] >= start_date) | (df["mm_dd"] <= end_date)]

        if df.empty:
            return DailyWindProfileResponse(
                spot_id=spot_id,
                timezone_offset_hours=tz_offset_hours,
                profiles=[],
            )

        # Cache dawn/dusk per unique UTC date to avoid redundant astral calls
        dawn_dusk_cache = {}

        profiles: List[DayProfile] = []
        for local_date, group in df.groupby("local_date"):
            # Get unique UTC dates covered by this local date's timestamps
            utc_dates = group["utc_time"].dt.date.unique()
            dawn_utc = None
            dusk_utc = None

            for utc_date in utc_dates:
                if utc_date not in dawn_dusk_cache:
                    dawn_dusk_cache[utc_date] = self._get_dawn_dusk_utc(
                        latitude, longitude, utc_date
                    )

            # Compute dawn/dusk in local time for this local date
            dawn_local, dusk_local = self._get_dawn_dusk_utc(
                latitude, longitude, local_date
            )
            if dawn_local is None:
                continue  # Polar night, skip

            # Convert dawn/dusk to local time
            dawn_local_ts = dawn_local + tz_offset
            dusk_local_ts = dusk_local + tz_offset

            # Filter to daylight hours using UTC dawn/dusk
            mask = (group["utc_time"].dt.tz_localize(timezone.utc) >= dawn_local) & \
                   (group["utc_time"].dt.tz_localize(timezone.utc) <= dusk_local)
            daylight = group[mask]

            if daylight.empty:
                continue

            # Extract local decimal hours and strength
            hours = (
                daylight["local_time"].dt.hour +
                daylight["local_time"].dt.minute / 60.0
            ).tolist()
            strengths = daylight["strength"].tolist()

            profiles.append(DayProfile(
                date=str(local_date),
                hours=hours,
                strength=[round(s, 1) for s in strengths],
            ))

        return DailyWindProfileResponse(
            spot_id=spot_id,
            timezone_offset_hours=round(tz_offset_hours, 2),
            profiles=profiles,
        )
