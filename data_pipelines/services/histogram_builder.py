"""Service for building wind histograms from processed data."""
from typing import Dict, Optional, Tuple
import numpy as np
import pandas as pd

from data_pipelines.config import WIND_BINS, DIRECTION_BINS, DAYS_OF_YEAR, FILTER_DAYLIGHT_HOURS
from data_pipelines.models.histogram import DailyHistogram1D, DailyHistogram2D
from data_pipelines.services.daylight_service import DaylightService


class HistogramBuilder:
    """Service for building daily wind histograms."""

    def __init__(
        self,
        wind_bins: list = None,
        direction_bins: list = None,
        filter_daylight: bool = FILTER_DAYLIGHT_HOURS,
    ):
        """
        Initialize histogram builder with bin configurations.

        Args:
            wind_bins: Wind speed bin edges
            direction_bins: Wind direction bin edges
            filter_daylight: Whether to filter out nighttime data
        """
        self.wind_bins = wind_bins or WIND_BINS
        self.direction_bins = direction_bins or DIRECTION_BINS
        self.filter_daylight = filter_daylight

        # Initialize daylight service for filtering
        self.daylight_service = DaylightService(filter_enabled=filter_daylight)

        # Accumulators for incremental histogram building
        # spot_id -> {day: counts_array}
        self._accum_1d: Dict[str, Dict[str, np.ndarray]] = {}
        self._accum_2d: Dict[str, Dict[str, np.ndarray]] = {}

        # Store spot coordinates for accumulation mode
        # spot_id -> (latitude, longitude)
        self._spot_coords: Dict[str, Tuple[float, float]] = {}

        self._num_strength_bins = len(self.wind_bins) - 1
        self._num_direction_bins = len(self.direction_bins) - 1

    def _get_day_of_year(self, timestamps: np.ndarray) -> np.ndarray:
        """Convert timestamps to MM-DD format strings."""
        # Convert to pandas datetime for easier manipulation
        dates = pd.to_datetime(timestamps)
        return np.array([d.strftime("%m-%d") for d in dates])

    def _apply_daylight_filter(
        self,
        timestamps: np.ndarray,
        wind_strength: np.ndarray,
        wind_direction: np.ndarray,
        latitude: Optional[float],
        longitude: Optional[float],
    ) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
        """
        Apply daylight filtering to wind data.

        Args:
            timestamps: Array of UTC timestamps
            wind_strength: Array of wind strength values
            wind_direction: Array of wind direction values
            latitude: Spot latitude (required if filter_daylight is True)
            longitude: Spot longitude (required if filter_daylight is True)

        Returns:
            Filtered (timestamps, wind_strength, wind_direction) arrays
        """
        if not self.filter_daylight or latitude is None or longitude is None:
            return timestamps, wind_strength, wind_direction

        # Create daylight mask
        mask = self.daylight_service.create_daylight_mask(latitude, longitude, timestamps)

        return timestamps[mask], wind_strength[mask], wind_direction[mask]

    def build_daily_1d_histogram(
        self,
        spot_id: str,
        timestamps: np.ndarray,
        wind_strength: np.ndarray,
        latitude: Optional[float] = None,
        longitude: Optional[float] = None,
    ) -> DailyHistogram1D:
        """
        Build daily 1D histograms of wind strength.

        Args:
            spot_id: ID of the spot
            timestamps: Array of timestamps (UTC)
            wind_strength: Array of wind strength values in knots
            latitude: Spot latitude for daylight filtering
            longitude: Spot longitude for daylight filtering

        Returns:
            DailyHistogram1D with aggregated daily counts
        """
        # Apply daylight filter if enabled
        timestamps, wind_strength, _ = self._apply_daylight_filter(
            timestamps, wind_strength, np.zeros_like(wind_strength), latitude, longitude
        )

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
        latitude: Optional[float] = None,
        longitude: Optional[float] = None,
    ) -> DailyHistogram2D:
        """
        Build daily 2D histograms of wind strength and direction.

        Args:
            spot_id: ID of the spot
            timestamps: Array of timestamps (UTC)
            wind_strength: Array of wind strength values in knots
            wind_direction: Array of wind direction values in degrees
            latitude: Spot latitude for daylight filtering
            longitude: Spot longitude for daylight filtering

        Returns:
            DailyHistogram2D with aggregated daily counts
        """
        # Apply daylight filter if enabled
        timestamps, wind_strength, wind_direction = self._apply_daylight_filter(
            timestamps, wind_strength, wind_direction, latitude, longitude
        )

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
        latitude: Optional[float] = None,
        longitude: Optional[float] = None,
    ) -> Tuple[DailyHistogram1D, DailyHistogram2D]:
        """
        Build both 1D and 2D histograms for a spot.

        Args:
            spot_id: ID of the spot
            timestamps: Array of timestamps (UTC)
            wind_strength: Array of wind strength values in knots
            wind_direction: Array of wind direction values in degrees
            latitude: Spot latitude for daylight filtering
            longitude: Spot longitude for daylight filtering

        Returns:
            Tuple of (DailyHistogram1D, DailyHistogram2D)
        """
        # Apply daylight filter once for both histograms
        filtered_ts, filtered_strength, filtered_direction = self._apply_daylight_filter(
            timestamps, wind_strength, wind_direction, latitude, longitude
        )

        # Build histograms from filtered data (no need to filter again)
        hist_1d = self.build_daily_1d_histogram(
            spot_id, filtered_ts, filtered_strength
        )
        hist_2d = self.build_daily_2d_histogram(
            spot_id, filtered_ts, filtered_strength, filtered_direction
        )
        return hist_1d, hist_2d

    # =========================================================================
    # Incremental accumulation methods for chunk-based processing
    # =========================================================================

    def register_spot_coordinates(
        self,
        spot_id: str,
        latitude: float,
        longitude: float,
    ) -> None:
        """
        Register spot coordinates for daylight filtering during accumulation.

        Args:
            spot_id: ID of the spot
            latitude: Spot latitude
            longitude: Spot longitude
        """
        self._spot_coords[spot_id] = (latitude, longitude)

    def accumulate(
        self,
        spot_id: str,
        timestamps: np.ndarray,
        wind_strength: np.ndarray,
        wind_direction: np.ndarray,
        latitude: Optional[float] = None,
        longitude: Optional[float] = None,
    ) -> None:
        """
        Accumulate histogram counts for a spot from a chunk of data.

        This method adds counts to running totals, allowing histogram building
        from multiple time chunks without keeping all data in memory.

        Args:
            spot_id: ID of the spot
            timestamps: Array of timestamps for this chunk (UTC)
            wind_strength: Array of wind strength values in knots
            wind_direction: Array of wind direction values in degrees
            latitude: Spot latitude for daylight filtering (or use registered coords)
            longitude: Spot longitude for daylight filtering (or use registered coords)
        """
        # Use registered coordinates if not provided
        if latitude is None or longitude is None:
            if spot_id in self._spot_coords:
                latitude, longitude = self._spot_coords[spot_id]

        # Apply daylight filter if enabled and coordinates available
        timestamps, wind_strength, wind_direction = self._apply_daylight_filter(
            timestamps, wind_strength, wind_direction, latitude, longitude
        )

        # Skip if no data remains after filtering
        if len(timestamps) == 0:
            return

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
