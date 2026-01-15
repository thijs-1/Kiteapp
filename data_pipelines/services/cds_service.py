"""Service for downloading ERA5 wind data from Copernicus Climate Data Store."""
from pathlib import Path
from typing import List, Optional
from datetime import datetime
import cdsapi
import xarray as xr

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

    def get_output_path(self, cell_id: str) -> Path:
        """Generate output path for combined data."""
        filename = f"era5_wind_{cell_id}.nc"
        return self.output_dir / filename

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
    ) -> Optional[Path]:
        """
        Download ERA5 wind data for a bounding box (year by year).

        Args:
            bbox: Bounding box to download data for
            cell_id: Unique identifier for the grid cell
            skip_existing: Skip download if combined file already exists

        Returns:
            Path to combined file, or None if skipped
        """
        combined_path = self.get_output_path(cell_id)

        if skip_existing and combined_path.exists():
            return None  # Combined file already exists

        years = self.get_year_range()
        yearly_files = []

        # Download each year separately
        for year in years:
            yearly_path = self.download_year(bbox, cell_id, year, skip_existing=True)
            if yearly_path and yearly_path.exists():
                yearly_files.append(yearly_path)

        if not yearly_files:
            print(f"  No yearly files downloaded for {cell_id}")
            return None

        # Combine yearly files into one
        print(f"  Combining {len(yearly_files)} yearly files...")
        datasets = [xr.open_dataset(f) for f in yearly_files]
        combined = xr.concat(datasets, dim="time")
        combined.to_netcdf(combined_path)

        # Close datasets
        for ds in datasets:
            ds.close()

        print(f"  Combined file saved: {combined_path}")
        return combined_path

    def download_for_cell(
        self,
        bbox: BoundingBox,
        cell_index: int,
        skip_existing: bool = True,
    ) -> Optional[Path]:
        """
        Download ERA5 data for a grid cell.

        Args:
            bbox: Expanded bounding box for the cell
            cell_index: Index of the grid cell (used for filename)
            skip_existing: Skip if file already exists

        Returns:
            Path to downloaded file, or None if skipped
        """
        cell_id = f"cell_{cell_index:04d}"
        return self.download_era5_wind(bbox, cell_id, skip_existing)
