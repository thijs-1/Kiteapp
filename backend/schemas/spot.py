"""Pydantic schemas for spots."""
from typing import List, Optional

from pydantic import BaseModel, Field


class NearestAirport(BaseModel):
    """One nearby airport with driving distance from a spot."""

    iata: str
    name: str
    municipality: Optional[str] = None
    iso_country: Optional[str] = None
    distance_km: float
    duration_minutes: float
    # Coordinates are optional for pickles enriched before coords were stored.
    latitude: Optional[float] = None
    longitude: Optional[float] = None


class SpotBase(BaseModel):
    """Base spot schema, used in list responses (kept lean: no airports)."""

    spot_id: str
    name: str
    latitude: float
    longitude: float
    country: Optional[str] = None


class SpotWithStats(SpotBase):
    """Spot with calculated statistics."""

    kiteable_percentage: float


class SpotDetail(SpotBase):
    """Single-spot detail, including nearest airports."""

    nearest_airports: List[NearestAirport] = Field(default_factory=list)


class SpotsMeta(BaseModel):
    """Dataset-level metadata about the loaded spots."""

    has_airport_data: bool
