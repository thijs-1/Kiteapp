"""Configuration constants for data pipelines."""
from pathlib import Path
import numpy as np

# Project paths
PROJECT_ROOT = Path(__file__).parent.parent
DATA_DIR = PROJECT_ROOT / "data"
RAW_DATA_DIR = DATA_DIR / "raw"
PROCESSED_DATA_DIR = DATA_DIR / "processed"
HISTOGRAMS_1D_FILE = PROCESSED_DATA_DIR / "histograms_1d.pkl"  # Single 3D array
HISTOGRAMS_2D_DIR = PROCESSED_DATA_DIR / "histograms_2d"

# Day of year mapping: list of "MM-DD" strings for all 366 days
DAYS_OF_YEAR = [f"{m:02d}-{d:02d}" for m in range(1, 13) for d in range(1, 32)
                if not (m == 2 and d > 29) and not (m in [4, 6, 9, 11] and d > 30)]

# Input data
INPUT_SPOTS_FILE = PROJECT_ROOT / "windguru_spots.pkl"
ENRICHED_SPOTS_FILE = PROCESSED_DATA_DIR / "spots.pkl"

# Wind strength bins: [0, 2.5, 5, 7.5, ..., 35, inf]
WIND_BINS = list(np.arange(0, 37.5, 2.5)) + [float('inf')]

# Direction bins: [-5, 5, 15, 25, ..., 345, 355] (36 bins of 10 degrees)
DIRECTION_BINS = list(range(-5, 360, 10))

# Grid configuration (larger cells to reduce CDS queue requests)
GRID_SIZE_LAT = 90  # degrees (2 cells latitude)
GRID_SIZE_LON = 60  # degrees (6 cells longitude)
GRID_EXPANSION_KM = 5  # km to expand each grid cell for downloads

# Unit conversion
MS_TO_KNOTS = 1.94384

# ERA5 configuration
ERA5_YEARS = 10  # Last 10 years of data
ERA5_DATASET = "reanalysis-era5-single-levels"
ERA5_VARIABLES = ["10m_u_component_of_wind", "10m_v_component_of_wind"]
