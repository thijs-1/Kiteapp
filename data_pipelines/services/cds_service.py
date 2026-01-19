"""Service for downloading ERA5 wind data from Copernicus Climate Data Store."""
from pathlib import Path
from typing import List, Optional
from datetime import datetime
import cdsapi

from data_pipelines.config import (
    RAW_DATA_DIR,
    ERA5_YEARS,
    ERA5_DATASET,
)
from data_pipelines.models.grid import BoundingBox


class CDSService:
    """Service for downloading ERA5 wind data from CDS."""

    def __init__(self, output_dir: Path = RAW_DATA_DIR):
        """Initialize CDS client."""
        self.client = cdsapi.Client()
        self.output_dir = output_dir
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def get_year_range(self) -> List[int]:
        """Get list of years to download (last ERA5_YEARS years)."""
        current_year = datetime.now().year
        # ERA5 data typically has a delay, use previous year as end
        end_year = current_year - 1
        start_year = end_year - ERA5_YEARS + 1
        return list(range(start_year, end_year + 1))

    def get_yearly_path(self, cell_id: str, year: int) -> Path:
        """Generate output path for yearly data."""
        filename = f"era5_wind_{cell_id}_{year}.nc"
        return self.output_dir / filename

    def download_year(
        self,
        bbox: BoundingBox,
        cell_id: str,
        year: int,
        skip_existing: bool = True,
    ) -> Optional[Path]:
        """
        Download one year of ERA5 10m wind data.

        Args:
            bbox: Bounding box to download data for
            cell_id: Unique identifier for the grid cell
            year: Year to download
            skip_existing: Skip download if file already exists

        Returns:
            Path to downloaded file, or None if skipped
        """
        output_path = self.get_yearly_path(cell_id, year)

        if skip_existing and output_path.exists():
            print(f"  Year {year} already exists, skipping")
            return output_path

        print(f"  Downloading year {year}...")

        # Only request the 10m u and v wind components
        request = {
            "product_type": "reanalysis",
            "variable": [
                "10m_u_component_of_wind",
                "10m_v_component_of_wind",
            ],
            "year": str(year),
            "month": [f"{m:02d}" for m in range(1, 13)],
            "day": [f"{d:02d}" for d in range(1, 32)],
            "time": [f"{h:02d}:00" for h in range(24)],
            "area": bbox.to_cds_area(),  # [north, west, south, east]
            "data_format": "netcdf",
        }

        self.client.retrieve(
            ERA5_DATASET,
            request,
            str(output_path),
        )

        return output_path

    def download_era5_wind(
        self,
        bbox: BoundingBox,
        cell_id: str,
        skip_existing: bool = True,
    ) -> List[Path]:
        """
        Download ERA5 wind data for a bounding box (one file per year).

        Args:
            bbox: Bounding box to download data for
            cell_id: Unique identifier for the grid cell
            skip_existing: Skip download if file already exists

        Returns:
            List of paths to yearly NetCDF files
        """
        years = self.get_year_range()
        downloaded_files = []

        for i, year in enumerate(years, 1):
            result = self.download_year(bbox, cell_id, year, skip_existing)
            if result:
                downloaded_files.append(result)
                print(f"    [{i}/{len(years)}] {year}: Done")

        return sorted(downloaded_files)

    def download_for_cell(
        self,
        bbox: BoundingBox,
        cell_index: int,
        skip_existing: bool = True,
    ) -> List[Path]:
        """
        Download ERA5 data for a grid cell.

        Args:
            bbox: Expanded bounding box for the cell
            cell_index: Index of the grid cell (used for filename)
            skip_existing: Skip if file already exists

        Returns:
            List of paths to yearly NetCDF files
        """
        cell_id = f"cell_{cell_index:04d}"
        return self.download_era5_wind(bbox, cell_id, skip_existing)

    def get_existing_files_for_cell(self, cell_index: int) -> List[Path]:
        """Get list of existing yearly files for a cell."""
        cell_id = f"cell_{cell_index:04d}"
        years = self.get_year_range()
        existing = []
        for year in years:
            path = self.get_yearly_path(cell_id, year)
            if path.exists():
                existing.append(path)
        return sorted(existing)
