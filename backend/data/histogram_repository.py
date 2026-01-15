"""Repository for histogram data access."""
from pathlib import Path
from typing import Optional, Dict, Any
import pickle

from backend.config import settings


class HistogramRepository:
    """Repository for accessing histogram data."""

    def __init__(
        self,
        histograms_1d_dir: Path = None,
        histograms_2d_dir: Path = None,
    ):
        """Initialize repository with paths to histogram directories."""
        self.histograms_1d_dir = histograms_1d_dir or settings.histograms_1d_dir
        self.histograms_2d_dir = histograms_2d_dir or settings.histograms_2d_dir

        # Cache for loaded histograms
        self._cache_1d: Dict[str, Dict[str, Any]] = {}
        self._cache_2d: Dict[str, Dict[str, Any]] = {}

    def _load_pickle(self, file_path: Path) -> Optional[Dict[str, Any]]:
        """Load a pickle file."""
        if not file_path.exists():
            return None
        with open(file_path, "rb") as f:
            return pickle.load(f)

    def get_1d_histogram(self, spot_id: str) -> Optional[Dict[str, Any]]:
        """
        Get 1D histogram data for a spot.

        Returns:
            Dict with keys: spot_id, bins, daily_counts
        """
        if spot_id in self._cache_1d:
            return self._cache_1d[spot_id]

        file_path = self.histograms_1d_dir / f"{spot_id}.pkl"
        data = self._load_pickle(file_path)

        if data:
            self._cache_1d[spot_id] = data

        return data

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
        file_1d = self.histograms_1d_dir / f"{spot_id}.pkl"
        file_2d = self.histograms_2d_dir / f"{spot_id}.pkl"
        return file_1d.exists() and file_2d.exists()

    def clear_cache(self) -> None:
        """Clear the histogram cache."""
        self._cache_1d.clear()
        self._cache_2d.clear()
