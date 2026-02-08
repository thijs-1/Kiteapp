"""Pydantic schemas for daily wind profile data."""
from pydantic import BaseModel
from typing import List


class DayProfile(BaseModel):
    """A single day's wind profile from dawn to dusk."""

    date: str  # "YYYY-MM-DD"
    hours: List[float]  # local time as decimal hours
    strength: List[float]  # wind speed in knots


class DailyWindProfileResponse(BaseModel):
    """Response schema for daily wind profiles."""

    spot_id: str
    timezone_offset_hours: float
    profiles: List[DayProfile]
