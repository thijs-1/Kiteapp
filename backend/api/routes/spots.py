"""API routes for spots."""
from typing import List, Optional
from fastapi import APIRouter, BackgroundTasks, Depends, Query, HTTPException
from fastapi.responses import Response

from backend.schemas.spot import SpotBase, SpotDetail, SpotsMeta, SpotWithStats
from backend.services.spot_service import SpotService
from backend.services.map_image_service import MapImageService
from backend.api.dependencies import get_spot_service, get_map_image_service

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
    max_airport_distance_km: Optional[float] = Query(
        None,
        ge=0,
        description=(
            "Keep only spots whose nearest airport is within this many km of driving. "
            "Spots without computed airport data are excluded. "
            "Ignored when the dataset has no airport data."
        ),
    ),
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
        max_airport_distance_km=max_airport_distance_km,
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


@router.get("/meta", response_model=SpotsMeta)
async def get_meta(
    spot_service: SpotService = Depends(get_spot_service),
) -> SpotsMeta:
    """Dataset-level metadata (e.g. whether airport data is available)."""
    return spot_service.get_meta()


@router.get("/{spot_id}/map-image")
def get_spot_map_image(
    spot_id: str,
    background_tasks: BackgroundTasks,
    spot_service: SpotService = Depends(get_spot_service),
    map_image_service: MapImageService = Depends(get_map_image_service),
) -> Response:
    """Satellite image of the box around a spot, disk-cached with LRU eviction.

    Cache hits are served immediately and re-fetched from Esri in the
    background (after the response) so the cache tracks recent imagery.
    Sync handler on purpose: FastAPI runs it in a threadpool, so the blocking
    Esri fetch on a cache miss doesn't stall the event loop.
    """
    spot = spot_service.get_spot(spot_id)
    if spot is None:
        raise HTTPException(status_code=404, detail="Spot not found")

    image = map_image_service.get_cached_image(spot_id)
    if image is not None:
        background_tasks.add_task(
            map_image_service.refresh_image, spot_id, spot.latitude, spot.longitude
        )
    else:
        image = map_image_service.refresh_image(spot_id, spot.latitude, spot.longitude)
        if image is None:
            raise HTTPException(status_code=502, detail="Failed to fetch map image")
    return Response(
        content=image,
        media_type="image/jpeg",
        headers={"Cache-Control": "public, max-age=86400"},
    )


@router.get("/{spot_id}", response_model=SpotDetail)
async def get_spot(
    spot_id: str,
    spot_service: SpotService = Depends(get_spot_service),
) -> SpotDetail:
    """Get a single spot by ID, including its nearest airports."""
    spot = spot_service.get_spot(spot_id)
    if spot is None:
        raise HTTPException(status_code=404, detail="Spot not found")
    return spot
