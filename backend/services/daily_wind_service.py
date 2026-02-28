"""Service for computing daily wind profiles from timeseries data."""
from datetime import timezone, timedelta, date
from typing import Optional, Dict, Tuple
import numpy as np
from astral import Observer
from astral.sun import sun

from backend.data.spot_repository import SpotRepository
from backend.data.timeseries_repository import TimeseriesRepository
from backend.schemas.daily_wind import DayProfile, DailyWindProfileResponse

DAYLIGHT_DEPRESSION_ANGLE = 6.0  # Civil twilight

_MAX_PROFILE_CACHE = 256


class DailyWindService:
    """Service for daily wind profile operations."""

    def __init__(
        self,
        spot_repo: SpotRepository = None,
        timeseries_repo: TimeseriesRepository = None,
    ):
        self.spot_repo = spot_repo or SpotRepository()
        self.timeseries_repo = timeseries_repo or TimeseriesRepository()
        self._dawn_dusk_cache: Dict[Tuple[float, float], Tuple[np.ndarray, np.ndarray]] = {}
        self._profile_cache: Dict[Tuple[str, str, str], DailyWindProfileResponse] = {}

    def _get_dawn_dusk_table(
        self, latitude: float, longitude: float,
    ) -> Tuple[np.ndarray, np.ndarray]:
        """
        Precompute dawn/dusk as local decimal hours for each day of year.

        Uses a leap year (2024) as reference so all 366 day-of-year slots are
        covered.  The per-DOY error across different calendar years is < 2 min,
        well within the hourly resolution of ERA5 data.

        Returns:
            (dawn_hours, dusk_hours) arrays of shape (366,).
            NaN entries indicate polar night (no daylight).
        """
        key = (round(latitude, 2), round(longitude, 2))
        if key in self._dawn_dusk_cache:
            return self._dawn_dusk_cache[key]

        tz_offset = timedelta(hours=longitude / 15.0)
        observer = Observer(latitude=latitude, longitude=longitude)
        dawn_hours = np.full(366, np.nan, dtype=np.float64)
        dusk_hours = np.full(366, np.nan, dtype=np.float64)

        base_date = date(2024, 1, 1)  # Leap year

        for doy in range(366):
            d = base_date + timedelta(days=doy)
            try:
                sun_times = sun(
                    observer, date=d, tzinfo=timezone.utc,
                    dawn_dusk_depression=DAYLIGHT_DEPRESSION_ANGLE,
                )
                dawn_local = sun_times["dawn"] + tz_offset
                dusk_local = sun_times["dusk"] + tz_offset
                dawn_hours[doy] = (
                    dawn_local.hour + dawn_local.minute / 60.0
                    + dawn_local.second / 3600.0
                )
                dusk_hours[doy] = (
                    dusk_local.hour + dusk_local.minute / 60.0
                    + dusk_local.second / 3600.0
                )
            except ValueError:
                # Polar day/night
                doy_1based = doy + 1
                is_northern_summer = 80 < doy_1based < 265
                is_polar_day = (
                    (latitude > 60 and is_northern_summer)
                    or (latitude < -60 and not is_northern_summer)
                )
                if is_polar_day:
                    dawn_hours[doy] = 0.0
                    dusk_hours[doy] = 24.0

        self._dawn_dusk_cache[key] = (dawn_hours, dusk_hours)
        return dawn_hours, dusk_hours

    def get_daily_wind_profiles(
        self,
        spot_id: str,
        start_date: str = "01-01",
        end_date: str = "12-31",
    ) -> Optional[DailyWindProfileResponse]:
        """
        Get daily wind profiles (dawn-to-dusk) for a spot.

        Optimised path: vectorised NumPy filtering replaces the previous
        per-day Python loop + per-day astral calls.  Results and intermediate
        dawn/dusk tables are cached so repeat requests are near-instant.
        """
        # --- result cache ---
        cache_key = (spot_id, start_date, end_date)
        if cache_key in self._profile_cache:
            return self._profile_cache[cache_key]

        spot = self.spot_repo.get_spot_by_id(spot_id)
        if spot is None:
            return None

        latitude = spot["latitude"]
        longitude = spot["longitude"]
        tz_offset_hours = longitude / 15.0

        ts_data = self.timeseries_repo.load_timeseries(spot_id)
        if ts_data is None:
            return None

        timestamps = ts_data["time"]       # datetime64[ns]
        strength = ts_data["strength"]     # float32

        if len(timestamps) == 0:
            result = DailyWindProfileResponse(
                spot_id=spot_id,
                timezone_offset_hours=round(tz_offset_hours, 2),
                profiles=[],
            )
            self._cache_result(cache_key, result)
            return result

        # ---- vectorised UTC → local conversion ----
        tz_offset_td = np.timedelta64(round(tz_offset_hours * 3600), 's')
        local_times = timestamps + tz_offset_td
        local_dates = local_times.astype('datetime64[D]')

        # ---- date-range filter (MM-DD) via month*100+day ----
        months_since_epoch = local_times.astype('datetime64[M]').astype(int)
        months = months_since_epoch % 12 + 1
        month_starts = local_times.astype('datetime64[M]').astype('datetime64[D]')
        days = (local_dates - month_starts).astype(int) + 1
        month_day_int = months * 100 + days

        start_val = int(start_date[:2]) * 100 + int(start_date[3:])
        end_val = int(end_date[:2]) * 100 + int(end_date[3:])

        if start_val <= end_val:
            range_mask = (month_day_int >= start_val) & (month_day_int <= end_val)
        else:
            range_mask = (month_day_int >= start_val) | (month_day_int <= end_val)

        # ---- daylight filter via precomputed dawn/dusk table ----
        year_starts = local_times.astype('datetime64[Y]').astype('datetime64[D]')
        doy = (local_dates - year_starts).astype(int)   # 0-indexed

        dawn_hours, dusk_hours = self._get_dawn_dusk_table(latitude, longitude)
        ts_dawn = dawn_hours[doy]
        ts_dusk = dusk_hours[doy]

        time_since_midnight = (
            (local_times - local_dates)
            .astype('timedelta64[s]')
            .astype(np.float64)
        )
        decimal_hours = time_since_midnight / 3600.0

        daylight_mask = (
            (~np.isnan(ts_dawn))
            & (decimal_hours >= ts_dawn)
            & (decimal_hours <= ts_dusk)
        )

        # ---- apply combined mask ----
        final_mask = range_mask & daylight_mask
        filtered_dates = local_dates[final_mask]
        filtered_hours = decimal_hours[final_mask]
        filtered_strength = strength[final_mask]

        if len(filtered_dates) == 0:
            result = DailyWindProfileResponse(
                spot_id=spot_id,
                timezone_offset_hours=round(tz_offset_hours, 2),
                profiles=[],
            )
            self._cache_result(cache_key, result)
            return result

        # ---- group by local date (data is chronologically sorted) ----
        unique_dates, start_indices = np.unique(filtered_dates, return_index=True)
        end_indices = np.append(start_indices[1:], len(filtered_dates))

        # Pre-round strength once instead of per-profile
        rounded_strength = np.round(filtered_strength, 1)

        profiles = []
        for i in range(len(unique_dates)):
            s, e = start_indices[i], end_indices[i]
            profiles.append(DayProfile(
                date=str(unique_dates[i]),
                hours=filtered_hours[s:e].tolist(),
                strength=rounded_strength[s:e].tolist(),
            ))

        result = DailyWindProfileResponse(
            spot_id=spot_id,
            timezone_offset_hours=round(tz_offset_hours, 2),
            profiles=profiles,
        )
        self._cache_result(cache_key, result)
        return result

    def _cache_result(
        self, key: Tuple[str, str, str], result: DailyWindProfileResponse,
    ):
        """Cache result with bounded size (FIFO eviction)."""
        if len(self._profile_cache) >= _MAX_PROFILE_CACHE:
            oldest = next(iter(self._profile_cache))
            del self._profile_cache[oldest]
        self._profile_cache[key] = result
