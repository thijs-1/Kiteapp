"""API routes for histograms."""
from fastapi import APIRouter, Depends, Query, HTTPException

from backend.schemas.histogram import HistogramResponse, KiteablePercentageResponse
from backend.services.histogram_service import HistogramService
from backend.api.dependencies import get_histogram_service

router = APIRouter(prefix="/spots/{spot_id}/histograms", tags=["histograms"])


@router.get("/daily", response_model=HistogramResponse)
async def get_daily_histograms(
    spot_id: str,
    start_date: str = Query("01-01", pattern=r"^\d{2}-\d{2}$"),
    end_date: str = Query("12-31", pattern=r"^\d{2}-\d{2}$"),
    histogram_service: HistogramService = Depends(get_histogram_service),
) -> HistogramResponse:
    """
    Get daily wind strength histograms for a spot.

    Returns histogram counts for each day in the specified date range.
    """
    result = histogram_service.get_daily_histograms(spot_id, start_date, end_date)
    if result is None:
        raise HTTPException(status_code=404, detail="Histogram data not found")
    return result


@router.get("/moving-average", response_model=HistogramResponse)
async def get_moving_average_histograms(
    spot_id: str,
    start_date: str = Query("01-01", pattern=r"^\d{2}-\d{2}$"),
    end_date: str = Query("12-31", pattern=r"^\d{2}-\d{2}$"),
    window_weeks: int = Query(2, ge=1, le=8, description="Window size in weeks"),
    histogram_service: HistogramService = Depends(get_histogram_service),
) -> HistogramResponse:
    """
    Get moving average wind strength histograms.

    Each day's histogram is averaged with surrounding days within the window.
    """
    result = histogram_service.get_moving_average_histograms(
        spot_id, start_date, end_date, window_weeks
    )
    if result is None:
        raise HTTPException(status_code=404, detail="Histogram data not found")
    return result


@router.get("/kiteable-percentage", response_model=KiteablePercentageResponse)
async def get_kiteable_percentage(
    spot_id: str,
    wind_min: float = Query(0, ge=0),
    wind_max: float = Query(100, description="Maximum wind speed (100 = infinity)"),
    start_date: str = Query("01-01", pattern=r"^\d{2}-\d{2}$"),
    end_date: str = Query("12-31", pattern=r"^\d{2}-\d{2}$"),
    moving_average: bool = Query(False, description="Use moving average"),
    window_weeks: int = Query(2, ge=1, le=8),
    histogram_service: HistogramService = Depends(get_histogram_service),
) -> KiteablePercentageResponse:
    """
    Get daily kiteable wind percentage.

    Returns the percentage of time wind is within the specified range
    for each day in the date range.
    """
    result = histogram_service.get_kiteable_percentage(
        spot_id=spot_id,
        wind_min=wind_min,
        wind_max=wind_max,
        start_date=start_date,
        end_date=end_date,
        moving_average=moving_average,
        window_weeks=window_weeks,
    )
    if result is None:
        raise HTTPException(status_code=404, detail="Histogram data not found")
    return result
