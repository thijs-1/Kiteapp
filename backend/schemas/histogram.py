"""Pydantic schemas for histogram data."""
from pydantic import BaseModel
from typing import Dict, List


class HistogramResponse(BaseModel):
    """Response schema for 1D histogram data."""

    spot_id: str
    bins: List[float]
    daily_data: Dict[str, List[int]]  # {"01-01": [counts...], ...}


class WindRoseResponse(BaseModel):
    """Response schema for wind rose (2D histogram) data."""

    spot_id: str
    strength_bins: List[float]
    direction_bins: List[float]
    data: List[List[float]]  # 2D array aggregated across date range


class KiteablePercentageResponse(BaseModel):
    """Response schema for kiteable percentage data."""

    spot_id: str
    wind_min: float
    wind_max: float
    daily_percentage: Dict[str, float]  # {"01-01": 75.5, ...}
