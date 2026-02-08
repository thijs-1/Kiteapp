"""Repository for timeseries data access."""
from pathlib import Path
from typing import Optional, Dict
import numpy as np

from backend.config import settings


class TimeseriesRepository:
    """Repository for accessing per-spot timeseries .npz files."""

    def __init__(self, timeseries_dir: Path = None):
        self.timeseries_dir = timeseries_dir or settings.timeseries_dir

    def load_timeseries(self, spot_id: str) -> Optional[Dict[str, np.ndarray]]:
        """
        Load timeseries data for a spot.

        Returns:
            Dict with keys: time (datetime64[ns]), strength (float32), direction (float32)
            or None if file doesn't exist.
        """
        file_path = self.timeseries_dir / f"{spot_id}.npz"
        if not file_path.exists():
            return None

        data = np.load(file_path)
        return {
            "time": data["time"],
            "strength": data["strength"],
            "direction": data["direction"],
        }
