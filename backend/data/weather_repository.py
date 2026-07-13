"""Repository for temperature and precipitation histogram data access."""
from pathlib import Path
from typing import Optional, Dict, Any, List
import pickle
import numpy as np

from backend.config import settings

TEMPERATURE = "temperature"
PRECIPITATION = "precipitation"
WEATHER_VARIABLES = (TEMPERATURE, PRECIPITATION)


class WeatherHistogramRepository:
    """
    Repository for accessing daily temperature/precipitation histograms.

    Each variable is stored as a single pickle with the same layout as the
    1D wind histograms: {spot_ids, bins, days, data} where data has shape
    (num_spots, 366, num_bins).
    """

    def __init__(
        self,
        temperature_file: Path = None,
        precipitation_file: Path = None,
    ):
        """Initialize repository with paths to histogram data."""
        self._files: Dict[str, Path] = {
            TEMPERATURE: temperature_file or settings.histograms_temperature_file,
            PRECIPITATION: precipitation_file or settings.histograms_precipitation_file,
        }
        # variable -> loaded dataset (None until loaded, or if file missing)
        self._loaded: Dict[str, bool] = {v: False for v in WEATHER_VARIABLES}
        self._data: Dict[str, Optional[Dict[str, Any]]] = {v: None for v in WEATHER_VARIABLES}

    def _load(self, variable: str) -> Optional[Dict[str, Any]]:
        """Load a variable's histogram file (lazily, once)."""
        if variable not in self._files:
            raise ValueError(f"Unknown weather variable: {variable}")

        if self._loaded[variable]:
            return self._data[variable]

        self._loaded[variable] = True
        file_path = self._files[variable]
        if not file_path.exists():
            return None

        with open(file_path, "rb") as f:
            raw = pickle.load(f)

        self._data[variable] = {
            "data": raw["data"],
            "spot_ids": raw["spot_ids"],
            "spot_to_idx": {sid: idx for idx, sid in enumerate(raw["spot_ids"])},
            "bins": raw["bins"],
            "days": raw["days"],
        }
        return self._data[variable]

    def get_bins(self, variable: str) -> Optional[List[float]]:
        """Get bin edges for a variable, or None if data is missing."""
        dataset = self._load(variable)
        return dataset["bins"] if dataset else None

    def get_histogram(self, variable: str, spot_id: str) -> Optional[Dict[str, Any]]:
        """
        Get daily histogram data for a spot.

        Returns:
            Dict with keys: spot_id, bins, daily_counts — or None if no data
            exists for the variable or spot.
        """
        dataset = self._load(variable)
        if dataset is None:
            return None

        idx = dataset["spot_to_idx"].get(spot_id)
        if idx is None:
            return None

        spot_data: np.ndarray = dataset["data"][idx]  # Shape: (366, num_bins)
        daily_counts = {
            day: spot_data[i].tolist()
            for i, day in enumerate(dataset["days"])
        }

        return {
            "spot_id": spot_id,
            "bins": dataset["bins"],
            "daily_counts": daily_counts,
        }

    def has_histogram(self, variable: str, spot_id: str) -> bool:
        """Check if histogram data exists for a spot."""
        dataset = self._load(variable)
        return dataset is not None and spot_id in dataset["spot_to_idx"]
