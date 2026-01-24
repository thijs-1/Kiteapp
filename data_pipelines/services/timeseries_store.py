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

    Files are designed to be appended to as chunks are processed.
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

    def append_spot_data(
        self,
        spot_id: str,
        time: np.ndarray,
        strength: np.ndarray,
        direction: np.ndarray,
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
        """
        path = self.get_spot_path(spot_id)

        # Load existing data if present
        if path.exists():
            existing = np.load(path)
            time = np.concatenate([existing["time"], time])
            strength = np.concatenate([existing["strength"], strength])
            direction = np.concatenate([existing["direction"], direction])

        # Sort by time (in case chunks arrive out of order)
        sort_idx = np.argsort(time)
        time = time[sort_idx]
        strength = strength[sort_idx].astype(np.float32)
        direction = direction[sort_idx].astype(np.float32)

        # Save
        np.savez_compressed(
            path,
            time=time,
            strength=strength,
            direction=direction,
        )

    def load_spot_data(self, spot_id: str) -> Optional[Dict[str, np.ndarray]]:
        """
        Load time series data for a spot.

        Args:
            spot_id: ID of the spot

        Returns:
            Dict with 'time', 'strength', 'direction' arrays, or None if not found
        """
        path = self.get_spot_path(spot_id)
        if not path.exists():
            return None

        data = np.load(path)
        return {
            "time": data["time"],
            "strength": data["strength"],
            "direction": data["direction"],
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
