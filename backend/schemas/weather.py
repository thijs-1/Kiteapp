"""Pydantic schemas for weather (temperature/precipitation) histogram data."""
from enum import Enum
from pydantic import BaseModel
from typing import Dict, List


class WeatherVariable(str, Enum):
    """Weather variables with daily histogram data."""

    temperature = "temperature"
    precipitation = "precipitation"


class WeatherHistogramResponse(BaseModel):
    """Response schema for daily weather histogram data."""

    spot_id: str
    variable: WeatherVariable
    unit: str  # "celsius" or "mm"
    bins: List[float]
    daily_data: Dict[str, List[float]]  # {"01-01": [counts...], ...}
