"""Service for building wind histograms from processed data."""
from typing import Dict, Tuple
import numpy as np
import pandas as pd

from data_pipelines.config import WIND_BINS, DIRECTION_BINS, DAYS_OF_YEAR
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

        # Accumulators for incremental histogram building
        # spot_id -> {day: counts_array}
        self._accum_1d: Dict[str, Dict[str, np.ndarray]] = {}
        self._accum_2d: Dict[str, Dict[str, np.ndarray]] = {}

        self._num_strength_bins = len(self.wind_bins) - 1
        self._num_direction_bins = len(self.direction_bins) - 1

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

    # =========================================================================
    # Incremental accumulation methods for chunk-based processing
    # =========================================================================

    def accumulate(
        self,
        spot_id: str,
        timestamps: np.ndarray,
        wind_strength: np.ndarray,
        wind_direction: np.ndarray,
    ) -> None:
        """
        Accumulate histogram counts for a spot from a chunk of data.

        This method adds counts to running totals, allowing histogram building
        from multiple time chunks without keeping all data in memory.

        Args:
            spot_id: ID of the spot
            timestamps: Array of timestamps for this chunk
            wind_strength: Array of wind strength values in knots
            wind_direction: Array of wind direction values in degrees
        """
        day_of_year = self._get_day_of_year(timestamps)
        unique_days = set(day_of_year)

        # Initialize accumulators for this spot if needed
        if spot_id not in self._accum_1d:
            self._accum_1d[spot_id] = {}
        if spot_id not in self._accum_2d:
            self._accum_2d[spot_id] = {}

        for day in unique_days:
            mask = day_of_year == day
            day_strength = wind_strength[mask]
            day_direction = wind_direction[mask]

            # Accumulate 1D histogram
            counts_1d, _ = np.histogram(day_strength, bins=self.wind_bins)
            if day in self._accum_1d[spot_id]:
                self._accum_1d[spot_id][day] += counts_1d
            else:
                self._accum_1d[spot_id][day] = counts_1d.astype(np.float32)

            # Accumulate 2D histogram
            counts_2d, _, _ = np.histogram2d(
                day_strength,
                day_direction,
                bins=[self.wind_bins, self.direction_bins],
            )
            if day in self._accum_2d[spot_id]:
                self._accum_2d[spot_id][day] += counts_2d
            else:
                self._accum_2d[spot_id][day] = counts_2d.astype(np.float32)

    def get_accumulated_1d(self, spot_id: str) -> DailyHistogram1D:
        """Get the accumulated 1D histogram for a spot."""
        if spot_id not in self._accum_1d:
            raise ValueError(f"No accumulated data for spot {spot_id}")

        return DailyHistogram1D(
            spot_id=spot_id,
            bins=self.wind_bins,
            daily_counts=self._accum_1d[spot_id],
        )

    def get_accumulated_2d(self, spot_id: str) -> DailyHistogram2D:
        """Get the accumulated 2D histogram for a spot."""
        if spot_id not in self._accum_2d:
            raise ValueError(f"No accumulated data for spot {spot_id}")

        return DailyHistogram2D(
            spot_id=spot_id,
            strength_bins=self.wind_bins,
            direction_bins=self.direction_bins,
            daily_counts=self._accum_2d[spot_id],
        )

    def get_accumulated_spot_ids(self) -> list:
        """Get list of spot IDs that have accumulated data."""
        return list(self._accum_1d.keys())

    def clear_accumulator(self, spot_id: str = None) -> None:
        """
        Clear accumulated data.

        Args:
            spot_id: If provided, clear only this spot. Otherwise clear all.
        """
        if spot_id:
            self._accum_1d.pop(spot_id, None)
            self._accum_2d.pop(spot_id, None)
        else:
            self._accum_1d.clear()
            self._accum_2d.clear()
