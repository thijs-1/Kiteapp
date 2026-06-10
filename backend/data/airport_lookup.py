"""Lookup of airport coordinates by IATA code, sourced from data/airports.csv.

The processed spots pickle stores only IATA + name + distance for each nearest
airport; coordinates are needed at request time so the frontend can render
airports on the spot map.
"""
from pathlib import Path
from typing import Dict, Optional, Tuple

import pandas as pd

from backend.config import settings


class AirportLookup:
    """In-memory IATA -> (latitude, longitude) lookup, lazy-loaded once."""

    def __init__(self, airports_file: Optional[Path] = None) -> None:
        self.airports_file = airports_file or settings.airports_file
        self._coords: Optional[Dict[str, Tuple[float, float]]] = None

    def _load(self) -> Dict[str, Tuple[float, float]]:
        if self._coords is not None:
            return self._coords
        try:
            df = pd.read_csv(self.airports_file, usecols=["iata_code", "latitude_deg", "longitude_deg"])
        except (FileNotFoundError, ValueError):
            self._coords = {}
            return self._coords
        coords: Dict[str, Tuple[float, float]] = {}
        for _, row in df.iterrows():
            iata = row["iata_code"]
            if pd.isna(iata):
                continue
            coords[str(iata).strip()] = (float(row["latitude_deg"]), float(row["longitude_deg"]))
        self._coords = coords
        return coords

    def get(self, iata: str) -> Optional[Tuple[float, float]]:
        return self._load().get(iata)
