"""Service for histogram operations."""
from typing import Dict, List, Optional
import math
import numpy as np

from backend.data.histogram_repository import HistogramRepository
from backend.config import settings


def _sanitize_for_json(bins: List[float]) -> List[float]:
    """Replace infinity values with 100 for JSON serialization."""
    return [100.0 if math.isinf(b) else b for b in bins]


class HistogramService:
    """Service for histogram operations."""

    def __init__(self, histogram_repo: HistogramRepository = None):
        """Initialize service with repository."""
        self.histogram_repo = histogram_repo or HistogramRepository()

    def _filter_dates(
        self,
        dates: List[str],
        start_date: str,
        end_date: str,
    ) -> List[str]:
        """Filter dates to those within the specified range."""
        if start_date <= end_date:
            return [d for d in dates if start_date <= d <= end_date]
        else:
            return [d for d in dates if d >= start_date or d <= end_date]

    def get_daily_histograms(
        self,
        spot_id: str,
        start_date: str = "01-01",
        end_date: str = "12-31",
    ) -> Optional[Dict]:
        """
        Get daily histograms for a spot within a date range.

        Returns:
            Dict with bins and filtered daily_data
        """
        hist_data = self.histogram_repo.get_1d_histogram(spot_id)
        if not hist_data:
            return None

        # Filter to date range
        all_dates = list(hist_data["daily_counts"].keys())
        filtered_dates = self._filter_dates(all_dates, start_date, end_date)

        filtered_counts = {
            date: hist_data["daily_counts"][date]
            for date in filtered_dates
            if date in hist_data["daily_counts"]
        }

        return {
            "spot_id": spot_id,
            "bins": _sanitize_for_json(hist_data["bins"]),
            "daily_data": filtered_counts,
        }

    def get_moving_average_histograms(
        self,
        spot_id: str,
        start_date: str = "01-01",
        end_date: str = "12-31",
        window_weeks: int = 2,
    ) -> Optional[Dict]:
        """
        Get moving average histograms for a spot.

        Each day's histogram is averaged with surrounding days within the window.

        Returns:
            Dict with bins and smoothed daily_data
        """
        hist_data = self.histogram_repo.get_1d_histogram(spot_id)
        if not hist_data:
            return None

        daily_counts = hist_data["daily_counts"]
        all_dates = sorted(daily_counts.keys())

        # Filter to date range
        filtered_dates = self._filter_dates(all_dates, start_date, end_date)

        # Window size in days
        window_days = window_weeks * 7

        smoothed_counts = {}

        for target_date in filtered_dates:
            # Find dates within window
            window_dates = self._get_window_dates(target_date, all_dates, window_days)

            # Average histograms within window
            histograms = [
                np.array(daily_counts[d])
                for d in window_dates
                if d in daily_counts
            ]

            if histograms:
                avg_histogram = np.mean(histograms, axis=0)
                smoothed_counts[target_date] = avg_histogram.tolist()

        return {
            "spot_id": spot_id,
            "bins": _sanitize_for_json(hist_data["bins"]),
            "daily_data": smoothed_counts,
        }

    def _get_window_dates(
        self,
        target_date: str,
        all_dates: List[str],
        window_days: int,
    ) -> List[str]:
        """Get dates within window of target date (handles year wrap)."""
        # Convert MM-DD to day of year (1-366)
        def to_day_number(date_str: str) -> int:
            month, day = map(int, date_str.split("-"))
            # Approximate day of year
            return (month - 1) * 30 + day

        target_day = to_day_number(target_date)
        window_dates = []

        for date in all_dates:
            date_day = to_day_number(date)

            # Calculate distance (handling year wrap)
            diff = abs(date_day - target_day)
            wrap_diff = 365 - diff

            if min(diff, wrap_diff) <= window_days:
                window_dates.append(date)

        return window_dates

    def get_kiteable_percentage(
        self,
        spot_id: str,
        wind_min: float = 0,
        wind_max: float = 100,
        start_date: str = "01-01",
        end_date: str = "12-31",
        moving_average: bool = False,
        window_weeks: int = 2,
    ) -> Optional[Dict]:
        """
        Calculate daily kiteable percentage.

        Returns:
            Dict with spot_id, wind_min, wind_max, and daily_percentage
        """
        if wind_max >= 100:
            wind_max = float("inf")

        if moving_average:
            hist_result = self.get_moving_average_histograms(
                spot_id, start_date, end_date, window_weeks
            )
        else:
            hist_result = self.get_daily_histograms(spot_id, start_date, end_date)

        if not hist_result:
            return None

        bins = hist_result["bins"]
        daily_data = hist_result["daily_data"]

        daily_percentage = {}

        for date, counts in daily_data.items():
            total = sum(counts)
            if total == 0:
                daily_percentage[date] = 0.0
                continue

            in_range = 0
            for i, count in enumerate(counts):
                bin_low = bins[i]
                bin_high = bins[i + 1] if i + 1 < len(bins) else float("inf")

                if bin_low >= wind_min and bin_high <= wind_max:
                    in_range += count
                elif bin_low < wind_max and bin_high > wind_min:
                    in_range += count

            daily_percentage[date] = round((in_range / total) * 100, 1)

        return {
            "spot_id": spot_id,
            "wind_min": wind_min,
            "wind_max": wind_max if wind_max != float("inf") else 100,
            "daily_percentage": daily_percentage,
        }
