"""Service for computing maximum sustained wind strength from time series."""
from collections import defaultdict
from typing import Dict, List, Optional, Tuple
import numpy as np
import pandas as pd

from data_pipelines.config import SUSTAINED_WIND_HOURS, FILTER_DAYLIGHT_HOURS
from data_pipelines.models.histogram import DailySustainedWind
from data_pipelines.services.daylight_service import DaylightService


class SustainedWindBuilder:
    """Service for computing daily maximum sustained wind strength.

    Computes the maximum wind strength that was sustained for at least
    a specified number of consecutive hours, aggregated by day of year.
    Only considers daylight hours when filtering is enabled.
    """

    def __init__(
        self,
        sustained_hours: int = SUSTAINED_WIND_HOURS,
        filter_daylight: bool = FILTER_DAYLIGHT_HOURS,
    ):
        """
        Initialize sustained wind builder.

        Args:
            sustained_hours: Minimum consecutive hours for sustained wind
            filter_daylight: Whether to filter out nighttime data
        """
        self.sustained_hours = sustained_hours
        self.filter_daylight = filter_daylight
        self.daylight_service = DaylightService(filter_enabled=filter_daylight)

    def _apply_daylight_filter(
        self,
        timestamps: np.ndarray,
        wind_strength: np.ndarray,
        latitude: Optional[float],
        longitude: Optional[float],
    ) -> Tuple[np.ndarray, np.ndarray]:
        """Apply daylight filtering to wind data."""
        if not self.filter_daylight or latitude is None or longitude is None:
            return timestamps, wind_strength

        mask = self.daylight_service.create_daylight_mask(latitude, longitude, timestamps)
        return timestamps[mask], wind_strength[mask]

    def _compute_rolling_min_max(
        self,
        wind_strength: np.ndarray,
        window_size: int,
    ) -> float:
        """
        Compute maximum of rolling minimums.

        For sustained wind: the rolling minimum over a window gives the
        "floor" of wind strength during that window (wind was at least
        this strong for the entire window). The maximum of these minimums
        across all windows gives the highest guaranteed sustained wind.

        Args:
            wind_strength: Array of wind strength values
            window_size: Number of consecutive hours for sustained wind

        Returns:
            Maximum sustained wind strength, or 0.0 if insufficient data
        """
        if len(wind_strength) < window_size:
            return 0.0

        # Use pandas for efficient rolling minimum
        series = pd.Series(wind_strength)
        rolling_min = series.rolling(window=window_size, min_periods=window_size).min()

        # Get maximum of rolling minimums (ignoring NaN from edges)
        max_sustained = rolling_min.max()
        return float(max_sustained) if not pd.isna(max_sustained) else 0.0

    def build_daily_sustained_wind(
        self,
        spot_id: str,
        timestamps: np.ndarray,
        wind_strength: np.ndarray,
        latitude: Optional[float] = None,
        longitude: Optional[float] = None,
    ) -> DailySustainedWind:
        """
        Build daily maximum sustained wind strength data.

        For each day of year, computes the maximum wind strength that was
        sustained for at least `sustained_hours` consecutive hours during
        daylight hours. Aggregates across years by taking the mean.

        Args:
            spot_id: ID of the spot
            timestamps: Array of timestamps (UTC)
            wind_strength: Array of wind strength values in knots
            latitude: Spot latitude for daylight filtering
            longitude: Spot longitude for daylight filtering

        Returns:
            DailySustainedWind with daily max sustained wind values
        """
        # Apply daylight filter if enabled
        timestamps, wind_strength = self._apply_daylight_filter(
            timestamps, wind_strength, latitude, longitude
        )

        if len(timestamps) == 0:
            return DailySustainedWind(
                spot_id=spot_id,
                sustained_hours=self.sustained_hours,
                daily_max_sustained={},
            )

        # Convert to pandas for easier date handling
        dates = pd.to_datetime(timestamps)

        # Group by full calendar date (YYYY-MM-DD) first
        # This ensures rolling window operates on consecutive hours within a day
        df = pd.DataFrame({
            'date': dates.date,
            'day_of_year': [d.strftime("%m-%d") for d in dates],
            'strength': wind_strength,
        })

        # Compute max sustained for each calendar date
        calendar_day_sustained: Dict[str, List[float]] = defaultdict(list)

        for calendar_date, group in df.groupby('date'):
            day_of_year = group['day_of_year'].iloc[0]
            day_strength = group['strength'].values

            # Compute max sustained wind for this calendar day
            max_sustained = self._compute_rolling_min_max(
                day_strength, self.sustained_hours
            )

            # Only include if we got a valid sustained wind value
            if max_sustained > 0:
                calendar_day_sustained[day_of_year].append(max_sustained)

        # Aggregate by day-of-year: take mean across all years
        daily_max_sustained: Dict[str, float] = {}
        for day_of_year, values in calendar_day_sustained.items():
            if values:
                daily_max_sustained[day_of_year] = float(np.mean(values))

        return DailySustainedWind(
            spot_id=spot_id,
            sustained_hours=self.sustained_hours,
            daily_max_sustained=daily_max_sustained,
        )
