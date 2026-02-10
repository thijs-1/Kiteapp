"""FastAPI dependencies for dependency injection."""
from functools import lru_cache

from backend.data.spot_repository import SpotRepository
from backend.data.histogram_repository import HistogramRepository
from backend.data.timeseries_repository import TimeseriesRepository
from backend.services.spot_service import SpotService
from backend.services.histogram_service import HistogramService
from backend.services.windrose_service import WindRoseService
from backend.services.daily_wind_service import DailyWindService


@lru_cache()
def get_spot_repository() -> SpotRepository:
    """Get cached spot repository instance."""
    return SpotRepository()


@lru_cache()
def get_histogram_repository() -> HistogramRepository:
    """Get cached histogram repository instance."""
    return HistogramRepository()


@lru_cache()
def get_spot_service() -> SpotService:
    """Get cached spot service instance."""
    return SpotService(
        spot_repo=get_spot_repository(),
        histogram_repo=get_histogram_repository(),
    )


def get_histogram_service() -> HistogramService:
    """Get histogram service instance."""
    return HistogramService(
        histogram_repo=get_histogram_repository(),
    )


def get_windrose_service() -> WindRoseService:
    """Get wind rose service instance."""
    return WindRoseService(
        histogram_repo=get_histogram_repository(),
    )


@lru_cache()
def get_timeseries_repository() -> TimeseriesRepository:
    """Get cached timeseries repository instance."""
    return TimeseriesRepository()


def get_daily_wind_service() -> DailyWindService:
    """Get daily wind service instance."""
    return DailyWindService(
        spot_repo=get_spot_repository(),
        timeseries_repo=get_timeseries_repository(),
    )
