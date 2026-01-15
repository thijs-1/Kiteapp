"""Repository for spot data access."""
from pathlib import Path
from typing import List, Optional, Dict
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

        self._loaded = True

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
