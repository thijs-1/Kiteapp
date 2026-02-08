"""API routes for daily wind profiles."""
from fastapi import APIRouter, Depends, Query, HTTPException

from backend.schemas.daily_wind import DailyWindProfileResponse
from backend.services.daily_wind_service import DailyWindService
from backend.api.dependencies import get_daily_wind_service

router = APIRouter(prefix="/spots/{spot_id}", tags=["daily-wind"])


@router.get("/daily-wind-profiles", response_model=DailyWindProfileResponse)
async def get_daily_wind_profiles(
    spot_id: str,
    start_date: str = Query("01-01", pattern=r"^\d{2}-\d{2}$"),
    end_date: str = Query("12-31", pattern=r"^\d{2}-\d{2}$"),
    daily_wind_service: DailyWindService = Depends(get_daily_wind_service),
) -> DailyWindProfileResponse:
    """
    Get daily wind profiles (dawn-to-dusk) for a spot.

    Returns individual day wind curves across all years in the date range.
    Each profile contains local-time hours and wind strength values.
    """
    result = daily_wind_service.get_daily_wind_profiles(
        spot_id, start_date, end_date
    )
    if result is None:
        raise HTTPException(status_code=404, detail="Timeseries data not found")
    return result
