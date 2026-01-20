"""Service for downloading ERA5 wind data from Google ARCO ERA5 (Zarr on GCS)."""
from pathlib import Path
from typing import List, Optional
from datetime import datetime
import xarray as xr
import numpy as np

from data_pipelines.config import (
    RAW_DATA_DIR,
    ERA5_YEARS,
)
from data_pipelines.models.grid import BoundingBox

# ARCO ERA5 Zarr store on Google Cloud Storage
# 6-hourly data (1959-2022) - fast to open, 4 samples per day
ARCO_ZARR_URL = "gs://gcp-public-data-arco-era5/ar/1959-2022-6h-1440x721.zarr"

# Variable name mapping: ARCO uses different names than CDS NetCDF output
ARCO_VAR_U10 = "10m_u_component_of_wind"
ARCO_VAR_V10 = "10m_v_component_of_wind"


class ARCOService:
    """Service for downloading ERA5 wind data from Google ARCO ERA5 Zarr store."""

    def __init__(self, output_dir: Path = RAW_DATA_DIR):
        """Initialize ARCO service."""
        self.output_dir = output_dir
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self._ds = None  # Lazy-loaded dataset

    def _get_dataset(self) -> xr.Dataset:
        """Get the ARCO dataset (lazy load on first access)."""
        if self._ds is None:
            print("Opening ARCO ERA5 Zarr store (this may take a moment)...")
            self._ds = xr.open_zarr(
                ARCO_ZARR_URL,
                chunks=None,  # Don't use dask chunking for simpler processing
                storage_options=dict(token="anon"),  # Anonymous access
            )
            print(f"  Dataset opened. Available: {str(self._ds.time.values[0])[:10]} to {str(self._ds.time.values[-1])[:10]}")
        return self._ds

    def get_year_range(self) -> List[int]:
        """Get list of years to download (last ERA5_YEARS years)."""
        current_year = datetime.now().year
        # ERA5 data typically has a delay, use previous year as end
        end_year = current_year - 1
        # ARCO 6-hourly data currently ends at 2021
        end_year = min(end_year, 2021)
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
        Download one year of ERA5 10m wind data from ARCO.

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

        print(f"  Fetching year {year} from ARCO...")

        ds = self._get_dataset()

        # Define time range for the year
        start_time = f"{year}-01-01"
        end_time = f"{year}-12-31T23:59:59"

        # Slice the dataset by time and spatial extent
        # ARCO uses 'time' coordinate, and longitude is 0-360
        subset = ds.sel(
            time=slice(start_time, end_time),
            latitude=slice(bbox.north, bbox.south),  # Latitude is descending in ERA5
            longitude=slice(
                bbox.west % 360 if bbox.west >= 0 else bbox.west + 360,
                bbox.east % 360 if bbox.east >= 0 else bbox.east + 360,
            ),
        )

        # Select only the wind variables we need
        subset = subset[[ARCO_VAR_U10, ARCO_VAR_V10]]

        # Print size info
        time_count = len(subset.time)
        lat_count = len(subset.latitude)
        lon_count = len(subset.longitude)
        estimated_mb = (time_count * lat_count * lon_count * 2 * 4) / 1024 / 1024
        print(f"    Sliced: {time_count} times x {lat_count} lat x {lon_count} lon (~{estimated_mb:.1f} MB)")
        print(f"    Chunk info: {subset[ARCO_VAR_U10].encoding.get('chunks', 'unknown')}")

        # Rename variables and coordinates to match CDS output format
        subset = subset.rename({
            ARCO_VAR_U10: "u10",
            ARCO_VAR_V10: "v10",
            "time": "valid_time",
        })

        # Convert longitude from 0-360 to -180 to 180 if needed
        lons = subset.longitude.values
        if lons.max() > 180:
            new_lons = np.where(lons > 180, lons - 360, lons)
            subset = subset.assign_coords(longitude=new_lons)
            subset = subset.sortby("longitude")

        # Load and save to NetCDF
        print(f"    Downloading and saving to {output_path.name}...")
        subset.load()  # Triggers actual download from GCS
        subset.to_netcdf(output_path)
        print(f"    Saved: {output_path.stat().st_size / 1024 / 1024:.1f} MB")
        subset.close()

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

    def close(self):
        """Close the dataset if open."""
        if self._ds is not None:
            self._ds.close()
            self._ds = None
