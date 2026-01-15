"""Service for building wind histograms from processed data."""
from typing import Dict, Tuple
import numpy as np
import pandas as pd

from data_pipelines.config import WIND_BINS, DIRECTION_BINS
from data_pipelines.models.histogram import DailyHistogram1D, DailyHistogram2D


class HistogramBuilder:
    """Service for building daily wind histograms."""

    def __init__(
        self,
        wind_bins: list = None,
        direction_bins: list = None,
    ):
        """Initialize histogram builder with bin configurations."""
        self.wind_bins = wind_bins or WIND_BINS
        self.direction_bins = direction_bins or DIRECTION_BINS

    def _get_day_of_year(self, timestamps: np.ndarray) -> np.ndarray:
        """Convert timestamps to MM-DD format strings."""
        # Convert to pandas datetime for easier manipulation
        dates = pd.to_datetime(timestamps)
        return np.array([d.strftime("%m-%d") for d in dates])

    def build_daily_1d_histogram(
        self,
        spot_id: str,
        timestamps: np.ndarray,
        wind_strength: np.ndarray,
    ) -> DailyHistogram1D:
        """
        Build daily 1D histograms of wind strength.

        Args:
            spot_id: ID of the spot
            timestamps: Array of timestamps
            wind_strength: Array of wind strength values in knots

        Returns:
            DailyHistogram1D with aggregated daily counts
        """
        day_of_year = self._get_day_of_year(timestamps)
        unique_days = sorted(set(day_of_year))

        daily_counts: Dict[str, np.ndarray] = {}

        for day in unique_days:
            mask = day_of_year == day
            day_strength = wind_strength[mask]

            # Create histogram for this day
            counts, _ = np.histogram(day_strength, bins=self.wind_bins)
            daily_counts[day] = counts

        return DailyHistogram1D(
            spot_id=spot_id,
            bins=self.wind_bins,
            daily_counts=daily_counts,
        )

    def build_daily_2d_histogram(
        self,
        spot_id: str,
        timestamps: np.ndarray,
        wind_strength: np.ndarray,
        wind_direction: np.ndarray,
    ) -> DailyHistogram2D:
        """
        Build daily 2D histograms of wind strength and direction.

        Args:
            spot_id: ID of the spot
            timestamps: Array of timestamps
            wind_strength: Array of wind strength values in knots
            wind_direction: Array of wind direction values in degrees

        Returns:
            DailyHistogram2D with aggregated daily counts
        """
        day_of_year = self._get_day_of_year(timestamps)
        unique_days = sorted(set(day_of_year))

        daily_counts: Dict[str, np.ndarray] = {}

        for day in unique_days:
            mask = day_of_year == day
            day_strength = wind_strength[mask]
            day_direction = wind_direction[mask]

            # Create 2D histogram for this day
            counts, _, _ = np.histogram2d(
                day_strength,
                day_direction,
                bins=[self.wind_bins, self.direction_bins],
            )
            daily_counts[day] = counts

        return DailyHistogram2D(
            spot_id=spot_id,
            strength_bins=self.wind_bins,
            direction_bins=self.direction_bins,
            daily_counts=daily_counts,
        )

    def build_histograms(
        self,
        spot_id: str,
        timestamps: np.ndarray,
        wind_strength: np.ndarray,
        wind_direction: np.ndarray,
    ) -> Tuple[DailyHistogram1D, DailyHistogram2D]:
        """
        Build both 1D and 2D histograms for a spot.

        Args:
            spot_id: ID of the spot
            timestamps: Array of timestamps
            wind_strength: Array of wind strength values in knots
            wind_direction: Array of wind direction values in degrees

        Returns:
            Tuple of (DailyHistogram1D, DailyHistogram2D)
        """
        hist_1d = self.build_daily_1d_histogram(
            spot_id, timestamps, wind_strength
        )
        hist_2d = self.build_daily_2d_histogram(
            spot_id, timestamps, wind_strength, wind_direction
        )
        return hist_1d, hist_2d
