"""Repository for spot data access."""
from pathlib import Path
from typing import List, Optional, Dict
import numpy as np
import pandas as pd

from backend.config import settings


class SpotRepository:
    """Repository for accessing spot data."""

    def __init__(self, spots_file: Path = None):
        """Initialize repository with path to spots file."""
        self.spots_file = spots_file or settings.spots_file
        self._df: Optional[pd.DataFrame] = None
        self._country_index: Dict[str, List[int]] = {}
        self._loaded = False

        # Parallel arrays for fast filtering (built on load)
        self._spot_ids: Optional[np.ndarray] = None
        self._names: Optional[np.ndarray] = None
        self._latitudes: Optional[np.ndarray] = None
        self._longitudes: Optional[np.ndarray] = None
        self._countries: Optional[np.ndarray] = None
        self._spot_id_to_idx: Dict[str, int] = {}
        self._names_lower: Optional[np.ndarray] = None

    def _load(self) -> None:
        """Load spots from pickle file."""
        if self._loaded:
            return

        import pickle
        with open(self.spots_file, "rb") as f:
            self._df = pickle.load(f)

        # Build country index for fast lookups
        for idx, row in self._df.iterrows():
            country = row["country"]
            if country not in self._country_index:
                self._country_index[country] = []
            self._country_index[country].append(idx)

        # Build parallel arrays for fast filtering
        self._spot_ids = self._df["spot_id"].values
        self._names = self._df["name"].values
        self._latitudes = self._df["latitude"].values.astype(np.float32)
        self._longitudes = self._df["longitude"].values.astype(np.float32)
        self._countries = self._df["country"].values
        self._spot_id_to_idx = {sid: i for i, sid in enumerate(self._spot_ids)}
        self._names_lower = np.array([
            str(n).lower() if pd.notna(n) else "" for n in self._names
        ])

        self._loaded = True

    def get_arrays(self):
        """Get parallel arrays for fast filtering. Returns (spot_ids, names, latitudes, longitudes, countries)."""
        self._load()
        return self._spot_ids, self._names, self._latitudes, self._longitudes, self._countries

    def get_spot_id_to_idx(self) -> Dict[str, int]:
        """Get mapping from spot_id to array index."""
        self._load()
        return self._spot_id_to_idx

    def get_country_mask(self, country: str) -> np.ndarray:
        """Get boolean mask for spots in a country."""
        self._load()
        return self._countries == country

    def get_name_mask(self, name: str) -> np.ndarray:
        """Get boolean mask for spots matching a name substring (case-insensitive)."""
        self._load()
        needle = name.lower()
        return np.array([needle in n for n in self._names_lower])

    @property
    def df(self) -> pd.DataFrame:
        """Get the spots DataFrame."""
        self._load()
        return self._df

    def get_all_spots(self) -> pd.DataFrame:
        """Get all spots."""
        return self.df.copy()

    def get_spot_by_id(self, spot_id: str) -> Optional[pd.Series]:
        """Get a single spot by ID."""
        matches = self.df[self.df["spot_id"] == spot_id]
        if len(matches) == 0:
            return None
        return matches.iloc[0]

    def filter_by_country(self, country: str) -> pd.DataFrame:
        """Filter spots by country code."""
        self._load()
        if country in self._country_index:
            indices = self._country_index[country]
            return self._df.loc[indices].copy()
        return pd.DataFrame()

    def search_by_name(self, name: str) -> pd.DataFrame:
        """Search spots by name (case-insensitive substring match)."""
        mask = self.df["name"].str.lower().str.contains(name.lower(), na=False)
        return self.df[mask].copy()

    def get_countries(self) -> List[str]:
        """Get list of all countries with spots."""
        self._load()
        return sorted(self._country_index.keys())

    def get_spot_ids(self) -> List[str]:
        """Get list of all spot IDs."""
        return self.df["spot_id"].tolist()
