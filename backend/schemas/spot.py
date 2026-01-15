"""Pydantic schemas for spots."""
from pydantic import BaseModel
from typing import Optional


class SpotBase(BaseModel):
    """Base spot schema."""

    spot_id: str
    name: str
    latitude: float
    longitude: float
    country: Optional[str] = None


class SpotWithStats(SpotBase):
    """Spot with calculated statistics."""

    kiteable_percentage: float
