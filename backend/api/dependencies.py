"""FastAPI dependencies for dependency injection."""
from functools import lru_cache

from backend.data.spot_repository import SpotRepository
from backend.data.histogram_repository import HistogramRepository
from backend.services.spot_service import SpotService
from backend.services.histogram_service import HistogramService
from backend.services.windrose_service import WindRoseService


@lru_cache()
def get_spot_repository() -> SpotRepository:
    """Get cached spot repository instance."""
    return SpotRepository()


@lru_cache()
def get_histogram_repository() -> HistogramRepository:
    """Get cached histogram repository instance."""
    return HistogramRepository()


def get_spot_service() -> SpotService:
    """Get spot service instance."""
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
