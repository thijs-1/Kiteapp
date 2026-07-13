"""Service for temperature and precipitation histogram operations."""
from typing import Dict, List, Optional
import math

from backend.data.weather_repository import (
    WeatherHistogramRepository,
    TEMPERATURE,
    PRECIPITATION,
)

# Units reported per variable
VARIABLE_UNITS = {
    TEMPERATURE: "celsius",
    PRECIPITATION: "mm",
}


def _sanitize_bins_for_json(bins: List[float]) -> List[float]:
    """
    Replace infinite bin edges with finite values for JSON serialization.

    The open-ended outer edges are replaced by extending the adjacent finite
    edge by one bin width (e.g. [..., 45, inf] with 2.5-wide bins -> [..., 45, 47.5]).
    """
    finite = [b for b in bins if math.isfinite(b)]
    if len(finite) < 2:
        return [b for b in bins if math.isfinite(b)]

    step = finite[1] - finite[0]
    sanitized = []
    for b in bins:
        if b == float("inf"):
            sanitized.append(finite[-1] + step)
        elif b == float("-inf"):
            sanitized.append(finite[0] - step)
        else:
            sanitized.append(b)
    return sanitized


class WeatherService:
    """Service for daily temperature/precipitation histogram operations."""

    def __init__(self, weather_repo: WeatherHistogramRepository = None):
        """Initialize service with repository."""
        self.weather_repo = weather_repo or WeatherHistogramRepository()

    def _filter_dates(
        self,
        dates: List[str],
        start_date: str,
        end_date: str,
    ) -> List[str]:
        """Filter dates to those within the specified range (handles year wrap)."""
        if start_date <= end_date:
            return [d for d in dates if start_date <= d <= end_date]
        else:
            return [d for d in dates if d >= start_date or d <= end_date]

    def get_daily_histograms(
        self,
        spot_id: str,
        variable: str,
        start_date: str = "01-01",
        end_date: str = "12-31",
    ) -> Optional[Dict]:
        """
        Get daily histograms of a weather variable for a spot within a date range.

        Args:
            spot_id: ID of the spot
            variable: "temperature" or "precipitation"
            start_date: Start of date range (MM-DD)
            end_date: End of date range (MM-DD)

        Returns:
            Dict with variable, unit, bins and filtered daily_data,
            or None if no data exists.
        """
        hist_data = self.weather_repo.get_histogram(variable, spot_id)
        if not hist_data:
            return None

        all_dates = list(hist_data["daily_counts"].keys())
        filtered_dates = self._filter_dates(all_dates, start_date, end_date)

        filtered_counts = {
            date: hist_data["daily_counts"][date]
            for date in filtered_dates
        }

        return {
            "spot_id": spot_id,
            "variable": variable,
            "unit": VARIABLE_UNITS[variable],
            "bins": _sanitize_bins_for_json(hist_data["bins"]),
            "daily_data": filtered_counts,
        }
