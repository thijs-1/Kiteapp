"""API routes for wind rose data."""
from fastapi import APIRouter, Depends, Query, HTTPException

from backend.schemas.histogram import WindRoseResponse
from backend.services.windrose_service import WindRoseService
from backend.api.dependencies import get_windrose_service

router = APIRouter(prefix="/spots/{spot_id}/windrose", tags=["windrose"])


@router.get("/", response_model=WindRoseResponse)
async def get_windrose(
    spot_id: str,
    start_date: str = Query("01-01", pattern=r"^\d{2}-\d{2}$"),
    end_date: str = Query("12-31", pattern=r"^\d{2}-\d{2}$"),
    windrose_service: WindRoseService = Depends(get_windrose_service),
) -> WindRoseResponse:
    """
    Get aggregated wind rose data for a spot.

    Returns 2D histogram of wind strength vs direction aggregated
    across the specified date range. Direction is "going to" (not from).
    """
    result = windrose_service.get_aggregated_windrose(spot_id, start_date, end_date)
    if result is None:
        raise HTTPException(status_code=404, detail="Wind rose data not found")
    return result
