"""Pydantic schemas for filter parameters."""
from pydantic import BaseModel, Field
from typing import Optional


class SpotFilterParams(BaseModel):
    """Parameters for filtering spots."""

    wind_min: float = Field(default=0.0, ge=0, description="Minimum wind speed in knots")
    wind_max: float = Field(default=100.0, description="Maximum wind speed in knots (100 = infinity)")
    start_date: str = Field(default="01-01", pattern=r"^\d{2}-\d{2}$", description="Start date (MM-DD)")
    end_date: str = Field(default="12-31", pattern=r"^\d{2}-\d{2}$", description="End date (MM-DD)")
    country: Optional[str] = Field(default=None, description="Filter by country code")
    name: Optional[str] = Field(default=None, description="Filter by spot name (substring match)")
    min_percentage: float = Field(default=75.0, ge=0, le=100, description="Minimum kiteable percentage")


class DateRangeParams(BaseModel):
    """Parameters for date range queries."""

    start_date: str = Field(default="01-01", pattern=r"^\d{2}-\d{2}$")
    end_date: str = Field(default="12-31", pattern=r"^\d{2}-\d{2}$")


class KiteableParams(BaseModel):
    """Parameters for kiteable percentage queries."""

    wind_min: float = Field(default=0.0, ge=0)
    wind_max: float = Field(default=100.0)
    start_date: str = Field(default="01-01", pattern=r"^\d{2}-\d{2}$")
    end_date: str = Field(default="12-31", pattern=r"^\d{2}-\d{2}$")
    moving_average: bool = Field(default=False)
    window_weeks: int = Field(default=2, ge=1, le=8)
