"""Service for storing and loading per-spot wind time series data."""
from pathlib import Path
from typing import Dict, List, Optional
import numpy as np

from data_pipelines.config import TIMESERIES_DIR


class TimeseriesStore:
    """
    Store for intermediate per-spot wind time series data.

    Each spot gets a .npz file containing:
    - time: array of timestamps (datetime64)
    - strength: array of wind strength in knots (float32)
    - direction: array of wind direction in degrees (float32)
    - temperature: array of 2m temperature in Celsius (float32, optional)
    - precipitation: array of hourly precipitation in mm (float32, optional)

    Files are designed to be appended to as chunks are processed. Temperature
    and precipitation are optional so files written before those variables
    were added keep working; gaps are stored as NaN to stay aligned with time.
    """

    def __init__(self, output_dir: Path = TIMESERIES_DIR):
        """Initialize the timeseries store."""
        self.output_dir = output_dir
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def get_spot_path(self, spot_id: str) -> Path:
        """Get the path for a spot's time series file."""
        return self.output_dir / f"{spot_id}.npz"

    def spot_exists(self, spot_id: str) -> bool:
        """Check if a spot's time series file exists."""
        return self.get_spot_path(spot_id).exists()

    @staticmethod
    def _concat_optional(
        existing_values: Optional[np.ndarray],
        existing_length: int,
        new_values: Optional[np.ndarray],
        new_length: int,
    ) -> Optional[np.ndarray]:
        """
        Concatenate an optional variable, padding missing sides with NaN.

        Keeps optional variables aligned with the time axis when either the
        existing file or the new chunk lacks the variable. Returns None when
        neither side has data.
        """
        if existing_values is None and new_values is None:
            return None

        if existing_values is None:
            existing_values = np.full(existing_length, np.nan, dtype=np.float32)
        if new_values is None:
            new_values = np.full(new_length, np.nan, dtype=np.float32)

        return np.concatenate([existing_values, new_values])

    def append_spot_data(
        self,
        spot_id: str,
        time: np.ndarray,
        strength: np.ndarray,
        direction: np.ndarray,
        temperature: Optional[np.ndarray] = None,
        precipitation: Optional[np.ndarray] = None,
    ) -> None:
        """
        Append time series data for a spot.

        If the spot already has data, the new data is concatenated.
        Data is automatically sorted by time after appending.

        Args:
            spot_id: ID of the spot
            time: Array of timestamps
            strength: Array of wind strength in knots
            direction: Array of wind direction in degrees
            temperature: Array of 2m temperature in Celsius (optional)
            precipitation: Array of hourly precipitation in mm (optional)
        """
        path = self.get_spot_path(spot_id)
        new_length = len(time)

        # Load existing data if present
        if path.exists():
            existing = np.load(path)
            existing_length = len(existing["time"])
            temperature = self._concat_optional(
                existing["temperature"] if "temperature" in existing else None,
                existing_length,
                temperature,
                new_length,
            )
            precipitation = self._concat_optional(
                existing["precipitation"] if "precipitation" in existing else None,
                existing_length,
                precipitation,
                new_length,
            )
            time = np.concatenate([existing["time"], time])
            strength = np.concatenate([existing["strength"], strength])
            direction = np.concatenate([existing["direction"], direction])

        # Sort by time (in case chunks arrive out of order)
        sort_idx = np.argsort(time)
        arrays = {
            "time": time[sort_idx],
            "strength": strength[sort_idx].astype(np.float32),
            "direction": direction[sort_idx].astype(np.float32),
        }
        if temperature is not None:
            arrays["temperature"] = temperature[sort_idx].astype(np.float32)
        if precipitation is not None:
            arrays["precipitation"] = precipitation[sort_idx].astype(np.float32)

        # Save
        np.savez_compressed(path, **arrays)

    def load_spot_data(self, spot_id: str) -> Optional[Dict[str, np.ndarray]]:
        """
        Load time series data for a spot.

        Args:
            spot_id: ID of the spot

        Returns:
            Dict with 'time', 'strength', 'direction' arrays plus 'temperature'
            and 'precipitation' (None if the file predates those variables),
            or None if not found
        """
        path = self.get_spot_path(spot_id)
        if not path.exists():
            return None

        data = np.load(path)
        return {
            "time": data["time"],
            "strength": data["strength"],
            "direction": data["direction"],
            "temperature": data["temperature"] if "temperature" in data else None,
            "precipitation": data["precipitation"] if "precipitation" in data else None,
        }

    def get_all_spot_ids(self) -> List[str]:
        """Get list of all spot IDs that have time series data."""
        return [p.stem for p in self.output_dir.glob("*.npz")]

    def delete_spot_data(self, spot_id: str) -> bool:
        """Delete time series data for a spot."""
        path = self.get_spot_path(spot_id)
        if path.exists():
            path.unlink()
            return True
        return False

    def clear_all(self) -> int:
        """
        Delete all time series files.

        Returns:
            Number of files deleted
        """
        count = 0
        for path in self.output_dir.glob("*.npz"):
            path.unlink()
            count += 1
        return count

    def get_total_size_mb(self) -> float:
        """Get total size of all time series files in MB."""
        total = sum(p.stat().st_size for p in self.output_dir.glob("*.npz"))
        return total / (1024 * 1024)
