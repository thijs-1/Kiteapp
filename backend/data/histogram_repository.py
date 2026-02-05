"""Repository for histogram data access."""
from pathlib import Path
from typing import Optional, Dict, Any, List
import pickle
import numpy as np

from backend.config import settings


class HistogramRepository:
    """Repository for accessing histogram data."""

    def __init__(
        self,
        histograms_1d_file: Path = None,
        histograms_2d_dir: Path = None,
        sustained_wind_file: Path = None,
    ):
        """Initialize repository with paths to histogram data."""
        self.histograms_1d_file = histograms_1d_file or settings.histograms_1d_file
        self.histograms_2d_dir = histograms_2d_dir or settings.histograms_2d_dir
        self.sustained_wind_file = sustained_wind_file or settings.sustained_wind_file

        # 1D histogram data (loaded lazily)
        self._1d_loaded = False
        self._1d_data: Optional[np.ndarray] = None  # Shape: (num_spots, 366, num_bins)
        self._1d_spot_ids: List[str] = []
        self._1d_spot_to_idx: Dict[str, int] = {}
        self._1d_bins: List[float] = []
        self._1d_days: List[str] = []
        self._1d_day_to_idx: Dict[str, int] = {}

        # Sustained wind data (loaded lazily)
        self._sustained_loaded = False
        self._sustained_data: Optional[np.ndarray] = None  # Shape: (num_spots, 366, num_bins)
        self._sustained_spot_ids: List[str] = []
        self._sustained_spot_to_idx: Dict[str, int] = {}
        self._sustained_bins: List[float] = []
        self._sustained_hours: int = 2

        # Cache for 2D histograms (per-spot, loaded on demand)
        self._cache_2d: Dict[str, Dict[str, Any]] = {}

    def preload(self) -> None:
        """Preload all filter data (1D histograms and sustained wind) on startup."""
        self._load_1d_data()
        self._load_sustained_data()

    def _load_1d_data(self) -> None:
        """Load the 1D histogram 3D array."""
        if self._1d_loaded:
            return

        if not self.histograms_1d_file.exists():
            self._1d_loaded = True
            return

        with open(self.histograms_1d_file, "rb") as f:
            data = pickle.load(f)

        self._1d_data = data["data"]
        self._1d_spot_ids = data["spot_ids"]
        self._1d_spot_to_idx = {sid: idx for idx, sid in enumerate(self._1d_spot_ids)}
        self._1d_bins = data["bins"]
        self._1d_days = data["days"]
        self._1d_day_to_idx = {day: idx for idx, day in enumerate(self._1d_days)}
        self._1d_loaded = True

    def _load_sustained_data(self) -> None:
        """Load the sustained wind 3D array."""
        if self._sustained_loaded:
            return

        if not self.sustained_wind_file.exists():
            self._sustained_loaded = True
            return

        with open(self.sustained_wind_file, "rb") as f:
            data = pickle.load(f)

        self._sustained_data = data["data"]
        self._sustained_spot_ids = data["spot_ids"]
        self._sustained_spot_to_idx = {sid: idx for idx, sid in enumerate(self._sustained_spot_ids)}
        self._sustained_bins = data["bins"]
        self._sustained_hours = data.get("sustained_hours", 2)
        self._sustained_loaded = True

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
        days = np.array(self._1d_days)

        if start_date <= end_date:
            mask = (days >= start_date) & (days <= end_date)
        else:
            # Wrap-around (e.g., Nov to Feb)
            mask = (days >= start_date) | (days <= end_date)

        return mask

    def get_1d_bin_mask(self, wind_min: float, wind_max: float) -> np.ndarray:
        """
        Get boolean mask for bins that fall within wind range.

        Returns:
            Boolean mask of shape (num_bins,)
        """
        self._load_1d_data()
        bins = np.array(self._1d_bins)
        num_bins = len(bins) - 1
        mask = np.zeros(num_bins, dtype=bool)

        for i in range(num_bins):
            bin_low = bins[i]
            bin_high = bins[i + 1]
            # Bin is included if it overlaps with [wind_min, wind_max]
            if bin_low < wind_max and bin_high > wind_min:
                mask[i] = True

        return mask

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

    # --- Sustained Wind Access ---

    def get_sustained_data(self) -> Optional[np.ndarray]:
        """Get the full sustained wind 3D array. Shape: (num_spots, 366, num_bins)"""
        self._load_sustained_data()
        return self._sustained_data

    def get_sustained_spot_ids(self) -> List[str]:
        """Get list of spot IDs in the same order as the sustained wind array."""
        self._load_sustained_data()
        return self._sustained_spot_ids

    def get_sustained_bins(self) -> List[float]:
        """Get wind speed bin edges for sustained wind data."""
        self._load_sustained_data()
        return self._sustained_bins

    def get_sustained_spot_index(self, spot_id: str) -> Optional[int]:
        """Get array index for a spot ID in sustained wind data."""
        self._load_sustained_data()
        return self._sustained_spot_to_idx.get(spot_id)

    def get_sustained_bin_index(self, wind_threshold: float) -> int:
        """
        Get the bin index for a wind threshold.

        Returns the index of the first bin where bin_low >= threshold.
        To get % of days with sustained wind >= threshold, sum percentages from this index onwards.
        """
        self._load_sustained_data()
        bins = self._sustained_bins
        for i, bin_low in enumerate(bins[:-1]):
            if bin_low >= wind_threshold:
                return i
        return len(bins) - 2  # Last valid bin index
