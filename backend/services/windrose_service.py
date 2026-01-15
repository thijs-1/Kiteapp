"""Service for wind rose operations."""
from typing import Dict, List, Optional
import numpy as np

from backend.data.histogram_repository import HistogramRepository


class WindRoseService:
    """Service for wind rose (2D histogram) operations."""

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

    def get_aggregated_windrose(
        self,
        spot_id: str,
        start_date: str = "01-01",
        end_date: str = "12-31",
    ) -> Optional[Dict]:
        """
        Get aggregated wind rose data for a spot.

        Sums all 2D histograms within the date range.

        Returns:
            Dict with strength_bins, direction_bins, and aggregated 2D data
        """
        hist_data = self.histogram_repo.get_2d_histogram(spot_id)
        if not hist_data:
            return None

        daily_counts = hist_data["daily_counts"]
        all_dates = list(daily_counts.keys())
        filtered_dates = self._filter_dates(all_dates, start_date, end_date)

        if not filtered_dates:
            return None

        # Get shape from first histogram
        first_hist = np.array(daily_counts[filtered_dates[0]])
        aggregated = np.zeros_like(first_hist, dtype=float)

        # Sum all histograms in range
        for date in filtered_dates:
            if date in daily_counts:
                aggregated += np.array(daily_counts[date])

        # Normalize to percentages
        total = aggregated.sum()
        if total > 0:
            aggregated = (aggregated / total) * 100

        return {
            "spot_id": spot_id,
            "strength_bins": hist_data["strength_bins"],
            "direction_bins": hist_data["direction_bins"],
            "data": aggregated.tolist(),
        }
