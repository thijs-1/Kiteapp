"""Repository for timeseries data access."""
from collections import OrderedDict
from pathlib import Path
from typing import Optional, Dict
import numpy as np

from backend.config import settings

_MAX_CACHE_SIZE = 128


class TimeseriesRepository:
    """Repository for accessing per-spot timeseries .npz files."""

    def __init__(self, timeseries_dir: Path = None):
        self.timeseries_dir = timeseries_dir or settings.timeseries_dir
        self._cache: OrderedDict[str, Dict[str, np.ndarray]] = OrderedDict()

    def load_timeseries(self, spot_id: str) -> Optional[Dict[str, np.ndarray]]:
        """
        Load timeseries data for a spot. Results are cached in memory (LRU).

        Returns:
            Dict with keys: time (datetime64[ns]), strength (float32), direction (float32)
            or None if file doesn't exist.
        """
        if spot_id in self._cache:
            self._cache.move_to_end(spot_id)
            return self._cache[spot_id]

        file_path = self.timeseries_dir / f"{spot_id}.npz"
        if not file_path.exists():
            return None

        data = np.load(file_path)
        result = {
            "time": data["time"],
            "strength": data["strength"],
            "direction": data["direction"],
        }

        self._cache[spot_id] = result
        if len(self._cache) > _MAX_CACHE_SIZE:
            self._cache.popitem(last=False)

        return result
