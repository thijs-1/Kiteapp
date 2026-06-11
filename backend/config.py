"""Backend configuration."""
from pathlib import Path
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings."""

    # Data paths
    project_root: Path = Path(__file__).parent.parent
    data_dir: Path = project_root / "data"
    processed_dir: Path = data_dir / "processed"
    spots_file: Path = processed_dir / "spots.pkl"
    histograms_1d_file: Path = processed_dir / "histograms_1d.pkl"  # Single 3D array
    histograms_2d_dir: Path = processed_dir / "histograms_2d"
    timeseries_dir: Path = data_dir / "timeseries"

    # Spot map images (satellite snapshot behind the wind rose),
    # fetched from Esri and disk-cached with LRU eviction
    map_image_cache_dir: Path = data_dir / "cache" / "map_images"
    map_image_cache_max_entries: int = 500
    map_image_refresh_after_days: float = 30.0
    map_image_half_box_m: float = 500.0
    map_image_size_px: int = 1024

    # API settings
    api_title: str = "Kiteapp API"
    api_version: str = "1.0.0"
    cors_origins: list = ["http://wheretokite.com"]

    # Default filter values
    default_wind_min: float = 0.0
    default_wind_max: float = float("inf")
    default_min_percentage: float = 75.0
    default_start_date: str = "01-01"
    default_end_date: str = "12-31"
    default_moving_avg_weeks: int = 1

    class Config:
        env_prefix = "KITEAPP_"


settings = Settings()
