"""Service for spot filtering and statistics."""
from typing import List, Optional, Dict, Tuple
from functools import lru_cache
import numpy as np
import pandas as pd

from backend.data.spot_repository import SpotRepository
from backend.data.histogram_repository import HistogramRepository
from backend.schemas.spot import SpotBase, SpotWithStats


class SpotService:
    """Service for spot operations."""

    def __init__(
        self,
        spot_repo: SpotRepository = None,
        histogram_repo: HistogramRepository = None,
    ):
        """Initialize service with repositories."""
        self.spot_repo = spot_repo or SpotRepository()
        self.histogram_repo = histogram_repo or HistogramRepository()
        self._filter_cache: Dict[tuple, List[SpotWithStats]] = {}

    def get_all_spots(self) -> List[SpotBase]:
        """Get all spots as SpotBase objects."""
        df = self.spot_repo.get_all_spots()
        return [
            SpotBase(
                spot_id=row["spot_id"],
                name=row["name"],
                latitude=row["latitude"],
                longitude=row["longitude"],
                country=row["country"],
            )
            for _, row in df.iterrows()
        ]

    def get_spot(self, spot_id: str) -> Optional[SpotBase]:
        """Get a single spot by ID."""
        row = self.spot_repo.get_spot_by_id(spot_id)
        if row is None:
            return None
        return SpotBase(
            spot_id=row["spot_id"],
            name=row["name"],
            latitude=row["latitude"],
            longitude=row["longitude"],
            country=row["country"],
        )

    def calculate_kiteable_percentage(
        self,
        spot_id: str,
        wind_min: float,
        wind_max: float,
        start_date: str,
        end_date: str,
    ) -> Optional[float]:
        """
        Calculate the percentage of time wind is within the specified range.

        Args:
            spot_id: Spot ID
            wind_min: Minimum wind speed in knots
            wind_max: Maximum wind speed in knots
            start_date: Start date (MM-DD)
            end_date: End date (MM-DD)

        Returns:
            Percentage of time wind is in range, or None if no data
        """
        # Get data from 3D array
        data = self.histogram_repo.get_1d_data()
        if data is None:
            return None

        idx = self.histogram_repo.get_spot_index(spot_id)
        if idx is None:
            return None

        # Get masks
        day_mask = self.histogram_repo.get_1d_day_indices(start_date, end_date)
        bin_mask = self.histogram_repo.get_1d_bin_mask(wind_min, wind_max)

        # Get spot data and apply masks
        spot_data = data[idx]  # Shape: (366, num_bins)
        filtered = spot_data[day_mask, :]  # Shape: (num_days_in_range, num_bins)

        total = filtered.sum()
        if total == 0:
            return None

        in_range = filtered[:, bin_mask].sum()
        return (in_range / total) * 100

    def _calculate_all_percentages_vectorized(
        self,
        wind_min: float,
        wind_max: float,
        start_date: str,
        end_date: str,
    ) -> Dict[str, float]:
        """
        Calculate kiteable percentage for ALL spots using vectorized operations.

        Returns:
            Dict mapping spot_id to percentage
        """
        data = self.histogram_repo.get_1d_data()
        if data is None:
            return {}

        spot_ids = self.histogram_repo.get_1d_spot_ids()
        if not spot_ids:
            return {}

        # Get masks
        day_mask = self.histogram_repo.get_1d_day_indices(start_date, end_date)
        bin_mask = self.histogram_repo.get_1d_bin_mask(wind_min, wind_max)

        # Apply day mask: data shape (num_spots, 366, num_bins) -> (num_spots, num_days, num_bins)
        filtered = data[:, day_mask, :]

        # Calculate totals per spot: sum over days and bins
        totals = filtered.sum(axis=(1, 2))  # Shape: (num_spots,)

        # Calculate in-range counts: sum over days, only selected bins
        in_range = filtered[:, :, bin_mask].sum(axis=(1, 2))  # Shape: (num_spots,)

        # Calculate percentages (avoid division by zero)
        with np.errstate(divide='ignore', invalid='ignore'):
            percentages = np.where(totals > 0, (in_range / totals) * 100, 0)

        # Build result dict
        return {spot_id: float(percentages[i]) for i, spot_id in enumerate(spot_ids)}

    def _calculate_sustained_percentages_vectorized(
        self,
        wind_threshold: float,
        start_date: str,
        end_date: str,
    ) -> Dict[str, float]:
        """
        Calculate percentage of days with sustained wind >= threshold for ALL spots.

        The sustained wind data stores percentages per bin. To get % of days with
        sustained wind >= threshold, we sum the percentages from the threshold bin onwards.

        Returns:
            Dict mapping spot_id to percentage of days with sustained wind >= threshold
        """
        data = self.histogram_repo.get_sustained_data()
        if data is None:
            return {}

        spot_ids = self.histogram_repo.get_sustained_spot_ids()
        if not spot_ids:
            return {}

        # Get day mask for date range
        day_mask = self.histogram_repo.get_1d_day_indices(start_date, end_date)

        # Get bin index for threshold
        bin_idx = self.histogram_repo.get_sustained_bin_index(wind_threshold)

        # Apply day mask: data shape (num_spots, 366, num_bins) -> (num_spots, num_days, num_bins)
        filtered = data[:, day_mask, :]

        # Sum percentages from threshold bin onwards, then average across days
        # Each day sums to 100%, so we sum bins >= threshold and average across days
        pct_above_threshold = filtered[:, :, bin_idx:].sum(axis=2)  # Shape: (num_spots, num_days)
        avg_pct = pct_above_threshold.mean(axis=1)  # Shape: (num_spots,)

        # Build result dict
        return {spot_id: float(avg_pct[i]) for i, spot_id in enumerate(spot_ids)}

    def filter_spots(
        self,
        wind_min: float = 0,
        wind_max: float = 100,
        start_date: str = "01-01",
        end_date: str = "12-31",
        country: Optional[str] = None,
        name: Optional[str] = None,
        min_percentage: float = 75,
        sustained_wind_min: float = 0,
        sustained_wind_days_min: float = 50,
    ) -> List[SpotWithStats]:
        """
        Filter spots based on criteria using vectorized operations.

        Args:
            wind_min: Minimum wind speed in knots
            wind_max: Maximum wind speed in knots (100 = infinity)
            start_date: Start date (MM-DD)
            end_date: End date (MM-DD)
            country: Filter by country code
            name: Filter by spot name (substring)
            min_percentage: Minimum kiteable percentage
            sustained_wind_min: Minimum sustained wind threshold (knots)
            sustained_wind_days_min: Minimum % of days with sustained wind >= threshold

        Returns:
            List of spots meeting criteria with their statistics
        """
        # Convert wind_max of 100 to infinity
        if wind_max >= 100:
            wind_max = float("inf")

        # Check result cache
        cache_key = (
            wind_min, wind_max, start_date, end_date,
            country, name, min_percentage,
            sustained_wind_min, sustained_wind_days_min,
        )
        if cache_key in self._filter_cache:
            return self._filter_cache[cache_key]

        result = self._filter_spots_uncached(
            wind_min, wind_max, start_date, end_date,
            country, name, min_percentage,
            sustained_wind_min, sustained_wind_days_min,
        )

        # Store in cache (bounded to prevent unbounded growth)
        if len(self._filter_cache) >= 512:
            # Evict oldest entry
            self._filter_cache.pop(next(iter(self._filter_cache)))
        self._filter_cache[cache_key] = result

        return result

    def _filter_spots_uncached(
        self,
        wind_min: float,
        wind_max: float,
        start_date: str,
        end_date: str,
        country: Optional[str],
        name: Optional[str],
        min_percentage: float,
        sustained_wind_min: float,
        sustained_wind_days_min: float,
    ) -> List[SpotWithStats]:
        """Core filtering logic using NumPy arrays (uncached)."""
        # Calculate percentages for ALL spots at once (vectorized) — returns arrays
        percentages = self._calculate_all_percentages_array(
            wind_min, wind_max, start_date, end_date
        )

        if percentages is None:
            return []

        histogram_spot_ids = self.histogram_repo.get_1d_spot_ids()
        spot_ids, names, latitudes, longitudes, countries = self.spot_repo.get_arrays()
        spot_id_to_idx = self.spot_repo.get_spot_id_to_idx()

        # Map histogram percentages to spot array order
        hist_id_to_idx = self.histogram_repo._1d_spot_to_idx
        pct_array = np.zeros(len(spot_ids), dtype=np.float32)
        for sid, h_idx in hist_id_to_idx.items():
            s_idx = spot_id_to_idx.get(sid)
            if s_idx is not None:
                pct_array[s_idx] = percentages[h_idx]

        # Build combined mask
        mask = pct_array >= min_percentage

        if country:
            mask &= self.spot_repo.get_country_mask(country)
        if name:
            mask &= self.spot_repo.get_name_mask(name)

        # Apply sustained wind filter
        if sustained_wind_min > 0:
            sustained_pct = self._calculate_sustained_percentages_array(
                sustained_wind_min, start_date, end_date
            )
            if sustained_pct is not None:
                sustained_spot_ids = self.histogram_repo.get_sustained_spot_ids()
                sust_id_to_idx = self.histogram_repo._sustained_spot_to_idx
                sust_array = np.zeros(len(spot_ids), dtype=np.float32)
                for sid, h_idx in sust_id_to_idx.items():
                    s_idx = spot_id_to_idx.get(sid)
                    if s_idx is not None:
                        sust_array[s_idx] = sustained_pct[h_idx]
                mask &= sust_array >= sustained_wind_days_min

        # Get passing indices, sort by percentage descending
        passing_idx = np.where(mask)[0]
        if len(passing_idx) == 0:
            return []

        order = np.argsort(-pct_array[passing_idx])
        result_idx = passing_idx[order]

        # Build result list directly (no DataFrame, no Pydantic overhead in hot path)
        return [
            SpotWithStats(
                spot_id=str(spot_ids[i]),
                name=str(names[i]),
                latitude=float(latitudes[i]),
                longitude=float(longitudes[i]),
                country=str(countries[i]) if pd.notna(countries[i]) else None,
                kiteable_percentage=round(float(pct_array[i]), 1),
            )
            for i in result_idx
        ]

    def _calculate_all_percentages_array(
        self,
        wind_min: float,
        wind_max: float,
        start_date: str,
        end_date: str,
    ) -> Optional[np.ndarray]:
        """
        Calculate kiteable percentage for ALL spots using prefix sums.

        Uses precomputed cumulative sums for O(spots × bins) regardless of date range size.

        Returns:
            NumPy array of percentages (num_spots,), or None if no data
        """
        # Get range sums via prefix sums: shape (num_spots, num_bins)
        range_sums = self.histogram_repo.get_range_sums(start_date, end_date)
        if range_sums is None:
            return None

        spot_ids = self.histogram_repo.get_1d_spot_ids()
        if not spot_ids:
            return None

        # Get cached bin mask
        bin_mask = self.histogram_repo.get_1d_bin_mask(wind_min, wind_max)

        # Totals per spot: sum over all bins
        totals = range_sums.sum(axis=1)  # Shape: (num_spots,)

        # In-range counts: sum over selected bins only
        in_range = range_sums[:, bin_mask].sum(axis=1)  # Shape: (num_spots,)

        # Calculate percentages (avoid division by zero)
        with np.errstate(divide='ignore', invalid='ignore'):
            percentages = np.where(totals > 0, (in_range / totals) * 100, 0).astype(np.float32)

        return percentages

    def _calculate_sustained_percentages_array(
        self,
        wind_threshold: float,
        start_date: str,
        end_date: str,
    ) -> Optional[np.ndarray]:
        """
        Calculate sustained wind percentages for ALL spots.

        Returns:
            NumPy array of percentages (num_spots,), or None if no data
        """
        data = self.histogram_repo.get_sustained_data()
        if data is None:
            return None

        spot_ids = self.histogram_repo.get_sustained_spot_ids()
        if not spot_ids:
            return None

        day_mask = self.histogram_repo.get_1d_day_indices(start_date, end_date)
        bin_idx = self.histogram_repo.get_sustained_bin_index(wind_threshold)

        filtered = data[:, day_mask, :]
        pct_above_threshold = filtered[:, :, bin_idx:].sum(axis=2)
        avg_pct = pct_above_threshold.mean(axis=1)

        return avg_pct.astype(np.float32)

    def get_countries(self) -> List[str]:
        """Get list of all countries."""
        return self.spot_repo.get_countries()
