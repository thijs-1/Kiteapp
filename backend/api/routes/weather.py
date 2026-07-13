"""API routes for weather (temperature/precipitation) histograms."""
from fastapi import APIRouter, Depends, Query, HTTPException

from backend.schemas.weather import WeatherHistogramResponse, WeatherVariable
from backend.services.weather_service import WeatherService
from backend.api.dependencies import get_weather_service

router = APIRouter(prefix="/spots/{spot_id}/weather", tags=["weather"])


@router.get("/{variable}/daily", response_model=WeatherHistogramResponse)
async def get_daily_weather_histograms(
    spot_id: str,
    variable: WeatherVariable,
    start_date: str = Query("01-01", pattern=r"^\d{2}-\d{2}$"),
    end_date: str = Query("12-31", pattern=r"^\d{2}-\d{2}$"),
    weather_service: WeatherService = Depends(get_weather_service),
) -> WeatherHistogramResponse:
    """
    Get daily daytime temperature or precipitation histograms for a spot.

    Temperature counts are hourly daytime samples in 2.5 degree Celsius bins;
    precipitation counts are hourly daytime samples in 2.5 mm bins.
    Returns histogram counts for each day in the specified date range.
    """
    result = weather_service.get_daily_histograms(
        spot_id, variable.value, start_date, end_date
    )
    if result is None:
        raise HTTPException(status_code=404, detail="Weather histogram data not found")
    return result
