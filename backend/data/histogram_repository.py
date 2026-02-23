"""Repository for histogram data access."""
from pathlib import Path
from typing import Optional, Dict, Any, List, Tuple
from functools import lru_cache
import pickle
import numpy as np

from backend.config import settings


class HistogramRepository:
    """Repository for accessing histogram data."""

    def __init__(
        self,
        histograms_1d_file: Path = None,
        histograms_2d_dir: Path = None,
    ):
        """Initialize repository with paths to histogram data."""
        self.histograms_1d_file = histograms_1d_file or settings.histograms_1d_file
        self.histograms_2d_dir = histograms_2d_dir or settings.histograms_2d_dir

        # 1D histogram data (loaded lazily)
        self._1d_loaded = False
        self._1d_data: Optional[np.ndarray] = None  # Shape: (num_spots, 366, num_bins)
        self._1d_spot_ids: List[str] = []
        self._1d_spot_to_idx: Dict[str, int] = {}
        self._1d_bins: List[float] = []
        self._1d_days: List[str] = []
        self._1d_day_to_idx: Dict[str, int] = {}

        # Cache for 2D histograms (per-spot, loaded on demand)
        self._cache_2d: Dict[str, Dict[str, Any]] = {}

    def preload(self) -> None:
        """Preload 1D histogram data on startup."""
        self._load_1d_data()

    def _load_1d_data(self) -> None:
        """Load the 1D histogram 3D array."""
        if self._1d_loaded:
            return

        if not self.histograms_1d_file.exists():
            self._1d_loaded = True
            return

        with open(self.histograms_1d_file, "rb") as f:
            data = pickle.load(f)

        self._1d_data = data["data"].astype(np.float32) if data["data"].dtype != np.float32 else data["data"]
        self._1d_spot_ids = data["spot_ids"]
        self._1d_spot_to_idx = {sid: idx for idx, sid in enumerate(self._1d_spot_ids)}
        self._1d_bins = data["bins"]
        self._1d_days = data["days"]
        self._1d_day_to_idx = {day: idx for idx, day in enumerate(self._1d_days)}

        # Precompute prefix sums along day axis: shape (num_spots, 367, num_bins)
        # prefix[s, d, b] = sum of data[s, 0:d, b]
        self._1d_prefix = np.zeros(
            (self._1d_data.shape[0], self._1d_data.shape[1] + 1, self._1d_data.shape[2]),
            dtype=np.float32,
        )
        np.cumsum(self._1d_data, axis=1, out=self._1d_prefix[:, 1:, :])

        self._1d_loaded = True

    def _load_pickle(self, file_path: Path) -> Optional[Dict[str, Any]]:
        """Load a pickle file."""
        if not file_path.exists():
            return None
        with open(file_path, "rb") as f:
            return pickle.load(f)

    # --- 1D Histogram Access (3D array) ---

    def get_1d_data(self) -> Optional[np.ndarray]:
        """Get the full 1D histogram 3D array. Shape: (num_spots, 366, num_bins)"""
        self._load_1d_data()
        return self._1d_data

    def get_1d_spot_ids(self) -> List[str]:
        """Get list of spot IDs in the same order as the 3D array."""
        self._load_1d_data()
        return self._1d_spot_ids

    def get_1d_bins(self) -> List[float]:
        """Get wind speed bin edges."""
        self._load_1d_data()
        return self._1d_bins

    def get_1d_days(self) -> List[str]:
        """Get list of day strings in order (MM-DD format)."""
        self._load_1d_data()
        return self._1d_days

    def get_1d_day_indices(self, start_date: str, end_date: str) -> np.ndarray:
        """
        Get array indices for a date range.

        Handles wrap-around (e.g., Nov 1 to Feb 28).

        Returns:
            Boolean mask of shape (366,) for days in range
        """
        self._load_1d_data()
        return self._get_day_mask_cached(start_date, end_date)

    @lru_cache(maxsize=512)
    def _get_day_mask_cached(self, start_date: str, end_date: str) -> np.ndarray:
        """Cached day mask computation."""
        days = np.array(self._1d_days)

        if start_date <= end_date:
            mask = (days >= start_date) & (days <= end_date)
        else:
            # Wrap-around (e.g., Nov to Feb)
            mask = (days >= start_date) | (days <= end_date)

        mask.flags.writeable = False  # Prevent mutation of cached array
        return mask

    def get_1d_bin_mask(self, wind_min: float, wind_max: float) -> np.ndarray:
        """
        Get boolean mask for bins that fall within wind range.

        Returns:
            Boolean mask of shape (num_bins,)
        """
        self._load_1d_data()
        return self._get_bin_mask_cached(wind_min, wind_max)

    @lru_cache(maxsize=256)
    def _get_bin_mask_cached(self, wind_min: float, wind_max: float) -> np.ndarray:
        """Cached bin mask computation."""
        bins = np.array(self._1d_bins)
        num_bins = len(bins) - 1
        mask = np.zeros(num_bins, dtype=bool)

        for i in range(num_bins):
            bin_low = bins[i]
            bin_high = bins[i + 1]
            # Bin is included if it overlaps with [wind_min, wind_max]
            if bin_low < wind_max and bin_high > wind_min:
                mask[i] = True

        mask.flags.writeable = False  # Prevent mutation of cached array
        return mask

    def get_day_range_indices(self, start_date: str, end_date: str) -> Tuple[int, int, bool]:
        """
        Convert date range to array indices.

        Returns:
            (start_idx, end_idx, wraps) where wraps=True means range crosses year boundary
        """
        self._load_1d_data()
        return self._get_day_range_cached(start_date, end_date)

    @lru_cache(maxsize=512)
    def _get_day_range_cached(self, start_date: str, end_date: str) -> Tuple[int, int, bool]:
        """Cached day range computation."""
        start_idx = self._1d_day_to_idx.get(start_date, 0)
        end_idx = self._1d_day_to_idx.get(end_date, len(self._1d_days) - 1)
        wraps = start_date > end_date
        return start_idx, end_idx, wraps

    def get_range_sums(self, start_date: str, end_date: str) -> Optional[np.ndarray]:
        """
        Get sum of histogram data over a date range using prefix sums.

        Returns:
            Array of shape (num_spots, num_bins) with sums over the date range
        """
        self._load_1d_data()
        if self._1d_data is None:
            return None

        start_idx, end_idx, wraps = self.get_day_range_indices(start_date, end_date)

        if not wraps:
            # Contiguous range: prefix[end+1] - prefix[start]
            return self._1d_prefix[:, end_idx + 1, :] - self._1d_prefix[:, start_idx, :]
        else:
            # Wrap-around: [start, last_day] + [0, end]
            num_days = self._1d_data.shape[1]
            return (
                (self._1d_prefix[:, num_days, :] - self._1d_prefix[:, start_idx, :])
                + self._1d_prefix[:, end_idx + 1, :]
            )

    def get_spot_index(self, spot_id: str) -> Optional[int]:
        """Get array index for a spot ID."""
        self._load_1d_data()
        return self._1d_spot_to_idx.get(spot_id)

    def get_1d_histogram(self, spot_id: str) -> Optional[Dict[str, Any]]:
        """
        Get 1D histogram data for a single spot (legacy format for compatibility).

        Returns:
            Dict with keys: spot_id, bins, daily_counts
        """
        self._load_1d_data()

        idx = self._1d_spot_to_idx.get(spot_id)
        if idx is None or self._1d_data is None:
            return None

        # Convert back to dict format for compatibility
        spot_data = self._1d_data[idx]  # Shape: (366, num_bins)
        daily_counts = {
            day: spot_data[i].tolist()
            for i, day in enumerate(self._1d_days)
        }

        return {
            "spot_id": spot_id,
            "bins": self._1d_bins,
            "daily_counts": daily_counts,
        }

    # --- 2D Histogram Access (per-spot files) ---

    def get_2d_histogram(self, spot_id: str) -> Optional[Dict[str, Any]]:
        """
        Get 2D histogram data for a spot.

        Returns:
            Dict with keys: spot_id, strength_bins, direction_bins, daily_counts
        """
        if spot_id in self._cache_2d:
            return self._cache_2d[spot_id]

        file_path = self.histograms_2d_dir / f"{spot_id}.pkl"
        data = self._load_pickle(file_path)

        if data:
            self._cache_2d[spot_id] = data

        return data

    def has_histogram(self, spot_id: str) -> bool:
        """Check if histogram data exists for a spot."""
        self._load_1d_data()
        has_1d = spot_id in self._1d_spot_to_idx
        file_2d = self.histograms_2d_dir / f"{spot_id}.pkl"
        return has_1d and file_2d.exists()

    def clear_cache(self) -> None:
        """Clear the 2D histogram cache."""
        self._cache_2d.clear()
