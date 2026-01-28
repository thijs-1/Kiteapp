"""API routes for spots."""
from typing import List, Optional
from fastapi import APIRouter, Depends, Query, HTTPException

from backend.schemas.spot import SpotBase, SpotWithStats
from backend.services.spot_service import SpotService
from backend.api.dependencies import get_spot_service

router = APIRouter(prefix="/spots", tags=["spots"])


@router.get("", response_model=List[SpotWithStats])
async def get_filtered_spots(
    wind_min: float = Query(0, ge=0, description="Minimum wind speed in knots"),
    wind_max: float = Query(100, description="Maximum wind speed (100 = infinity)"),
    start_date: str = Query("01-01", pattern=r"^\d{2}-\d{2}$", description="Start date (MM-DD)"),
    end_date: str = Query("12-31", pattern=r"^\d{2}-\d{2}$", description="End date (MM-DD)"),
    country: Optional[str] = Query(None, description="Filter by country code"),
    name: Optional[str] = Query(None, description="Filter by spot name"),
    min_percentage: float = Query(75, ge=0, le=100, description="Minimum kiteable percentage"),
    spot_service: SpotService = Depends(get_spot_service),
) -> List[SpotWithStats]:
    """
    Get spots filtered by wind conditions and other criteria.

    Returns spots where wind is within the specified range for at least
    min_percentage of the time during the specified date range.
    """
    return spot_service.filter_spots(
        wind_min=wind_min,
        wind_max=wind_max,
        start_date=start_date,
        end_date=end_date,
        country=country,
        name=name,
        min_percentage=min_percentage,
    )


@router.get("/all", response_model=List[SpotBase])
async def get_all_spots(
    spot_service: SpotService = Depends(get_spot_service),
) -> List[SpotBase]:
    """Get all spots without filtering."""
    return spot_service.get_all_spots()


@router.get("/countries", response_model=List[str])
async def get_countries(
    spot_service: SpotService = Depends(get_spot_service),
) -> List[str]:
    """Get list of all countries with spots."""
    return spot_service.get_countries()


@router.get("/{spot_id}", response_model=SpotBase)
async def get_spot(
    spot_id: str,
    spot_service: SpotService = Depends(get_spot_service),
) -> SpotBase:
    """Get a single spot by ID."""
    spot = spot_service.get_spot(spot_id)
    if spot is None:
        raise HTTPException(status_code=404, detail="Spot not found")
    return spot
