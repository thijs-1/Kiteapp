"""Service for downloading ERA5 wind data from Google ARCO ERA5 (Zarr on GCS)."""
from pathlib import Path
from typing import List, Optional
from datetime import datetime, timedelta
import xarray as xr
import numpy as np

try:
    import psutil
    _HAS_PSUTIL = True
except ImportError:
    _HAS_PSUTIL = False

from data_pipelines.config import (
    RAW_DATA_DIR,
    ERA5_YEARS,
    ARCO_CHUNK_MONTHS,
)

# ARCO ERA5 Zarr store on Google Cloud Storage
# Hourly data at 0.25° resolution - includes surface variables
ARCO_ZARR_URL = "gs://gcp-public-data-arco-era5/ar/full_37-1h-0p25deg-chunk-1.zarr-v3"

# Variable names in the hourly dataset (full names in this dataset)
ARCO_VAR_U10 = "10m_u_component_of_wind"
ARCO_VAR_V10 = "10m_v_component_of_wind"

# Bytes per hour of global ERA5 data: 721 lat × 1440 lon × 2 vars × 4 bytes (float32)
_BYTES_PER_HOUR_GLOBAL = 721 * 1440 * 2 * 4  # ~7.93 MB


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
            print("Opening ARCO ERA5 Zarr store (hourly 0.25° resolution)...")
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
        # ARCO hourly data may have a different end date - will be checked at download time
        start_year = end_year - ERA5_YEARS + 1
        return list(range(start_year, end_year + 1))

    def get_chunk_periods(self, test_days: int = None) -> List[tuple]:
        """
        Get list of (start_date, end_date) tuples for chunk-based downloads.

        Uses 3-month (quarterly) chunks for ~9 GB compressed files.

        Args:
            test_days: If provided, return a single chunk of this many days (for testing)

        Returns:
            List of (start_date, end_date) tuples as strings in 'YYYY-MM-DD' format
        """
        if test_days:
            # Test mode: use quarterly chunks within the test range
            start = datetime(2020, 1, 1)
            end = start + timedelta(days=test_days - 1)
        else:
            years = self.get_year_range()
            start = datetime(years[0], 1, 1)
            end = datetime(years[-1], 12, 31)

        # Build quarterly chunks covering the date range
        periods = []
        # Quarter boundaries: (month_start, month_end, last_day)
        quarters = [(1, 3, 31), (4, 6, 30), (7, 9, 30), (10, 12, 31)]

        current_year = start.year
        while datetime(current_year, 1, 1) <= end:
            for q_start_month, q_end_month, q_last_day in quarters:
                q_start = datetime(current_year, q_start_month, 1)
                q_end = datetime(current_year, q_end_month, q_last_day)

                # Skip quarters entirely before start or after end
                if q_end < start or q_start > end:
                    continue

                # Clamp to actual range
                actual_start = max(q_start, start)
                actual_end = min(q_end, end)

                periods.append((
                    actual_start.strftime("%Y-%m-%d"),
                    actual_end.strftime("%Y-%m-%d"),
                ))
            current_year += 1

        return periods

    def get_chunk_path(self, start_date: str, end_date: str) -> Path:
        """Generate output path for a chunk file."""
        # Extract year and month info for filename
        start_year = start_date[:4]
        start_month = start_date[5:7]
        end_month = end_date[5:7]
        filename = f"era5_wind_global_{start_year}_{start_month}-{end_month}.nc"
        return self.output_dir / filename

    def get_cell_chunk_path(self, cell_id: str, start_date: str, end_date: str) -> Path:
        """Generate output path for a cell+time chunk file."""
        start_year = start_date[:4]
        start_month = start_date[5:7]
        end_month = end_date[5:7]
        filename = f"era5_wind_{cell_id}_{start_year}_{start_month}-{end_month}.nc"
        return self.output_dir / filename

    def _get_available_memory_bytes(self) -> int:
        """Get available system memory in bytes."""
        if _HAS_PSUTIL:
            mem = psutil.virtual_memory()
            print(f"  System RAM: {mem.total / 1024**3:.1f} GB total, "
                  f"{mem.available / 1024**3:.1f} GB available")
            return mem.available
        else:
            print("  Warning: psutil not installed, assuming 4 GB available RAM")
            return 4 * 1024**3

    def _get_max_chunk_hours(self) -> int:
        """Calculate max hours per sub-chunk to stay within half of available RAM."""
        available = self._get_available_memory_bytes()
        usable = available // 2

        max_hours = int(usable // _BYTES_PER_HOUR_GLOBAL)
        # Round down to nearest day, clamp to [24 hours, 2160 hours (90 days)]
        max_hours = max(24, min(max_hours, 2160))
        max_hours = (max_hours // 24) * 24

        print(f"  Max chunk size: {max_hours} hours ({max_hours // 24} days)")
        return max_hours

    def _split_period_into_sub_chunks(
        self, start_date: str, end_date: str, max_hours: int
    ) -> List[tuple]:
        """Split a date range into sub-chunks that each fit in memory."""
        start = datetime.strptime(start_date, "%Y-%m-%d")
        end = datetime.strptime(end_date, "%Y-%m-%d")
        max_days = max_hours // 24

        chunks = []
        current = start
        while current <= end:
            chunk_end = min(current + timedelta(days=max_days - 1), end)
            chunks.append((
                current.strftime("%Y-%m-%d"),
                chunk_end.strftime("%Y-%m-%d"),
            ))
            current = chunk_end + timedelta(days=1)

        return chunks

    def _fetch_global_subset(self, ds, start_date: str, end_date: str):
        """Select a global time slice, rename variables, and convert coordinates."""
        subset = ds.sel(time=slice(start_date, end_date))[[ARCO_VAR_U10, ARCO_VAR_V10]]

        time_count = len(subset.time)
        lat_count = len(subset.latitude)
        lon_count = len(subset.longitude)
        estimated_gb = (time_count * lat_count * lon_count * 2 * 4) / 1024**3
        print(f"      Size: {time_count} hours x {lat_count} lat x {lon_count} lon "
              f"(~{estimated_gb:.1f} GB uncompressed)")

        subset = subset.rename({
            ARCO_VAR_U10: "u10",
            ARCO_VAR_V10: "v10",
            "time": "valid_time",
        })

        # Convert longitude from 0-360 to -180 to 180
        lons = subset.longitude.values
        if lons.max() > 180:
            new_lons = np.where(lons > 180, lons - 360, lons)
            subset = subset.assign_coords(longitude=new_lons)
            subset = subset.sortby("longitude")

        return subset

    def download_global_period(
        self,
        start_date: str,
        end_date: str,
        skip_existing: bool = True,
    ) -> Optional[Path]:
        """
        Download GLOBAL ERA5 10m wind data for a time period.

        Downloads the entire globe (no spatial slicing) which is efficient
        since ARCO Zarr chunks are (1, 721, 1440) = 1 hour x full globe.

        Automatically splits into memory-safe sub-chunks based on available
        RAM (uses at most half of available memory per sub-chunk).

        Args:
            start_date: Start date in 'YYYY-MM-DD' format
            end_date: End date in 'YYYY-MM-DD' format
            skip_existing: Skip download if file already exists

        Returns:
            Path to downloaded file, or None if failed
        """
        output_path = self.get_chunk_path(start_date, end_date)

        if skip_existing and output_path.exists():
            print(f"  Global chunk {start_date} to {end_date} already exists")
            return output_path

        print(f"  Downloading GLOBAL {start_date} to {end_date}...")

        ds = self._get_dataset()

        # Check if the requested dates are within the dataset's time range
        ds_start = str(ds.time.values[0])[:10]
        ds_end = str(ds.time.values[-1])[:10]

        actual_start = start_date
        actual_end = end_date

        if start_date < ds_start:
            print(f"    Warning: Requested start {start_date} before dataset start {ds_start}")
            actual_start = ds_start
        if end_date > ds_end:
            print(f"    Warning: Requested end {end_date} after dataset end {ds_end}")
            actual_end = ds_end

        # Calculate memory-safe sub-chunk size
        max_hours = self._get_max_chunk_hours()
        sub_chunks = self._split_period_into_sub_chunks(actual_start, actual_end, max_hours)

        if len(sub_chunks) == 1:
            # Single chunk fits in memory — download directly
            print(f"    Downloading and saving to {output_path.name}...")
            subset = self._fetch_global_subset(ds, actual_start, actual_end)
            subset.load()
            subset.to_netcdf(output_path)
            del subset
        else:
            # Multiple sub-chunks needed — download to temp files, then combine
            print(f"    Splitting into {len(sub_chunks)} sub-chunks to fit in memory")
            temp_files = []
            try:
                for i, (sub_start, sub_end) in enumerate(sub_chunks):
                    print(f"    Sub-chunk {i + 1}/{len(sub_chunks)}: {sub_start} to {sub_end}")
                    subset = self._fetch_global_subset(ds, sub_start, sub_end)
                    subset.load()

                    temp_path = output_path.parent / f"{output_path.stem}_part{i}.nc"
                    subset.to_netcdf(temp_path)
                    chunk_mb = temp_path.stat().st_size / 1024**2
                    print(f"      Saved temp: {chunk_mb:.0f} MB")
                    del subset

                    temp_files.append(temp_path)

                # Combine temp files into final output using dask to stream
                print(f"    Combining {len(temp_files)} parts into {output_path.name}...")
                import dask
                combined = xr.open_mfdataset(
                    [str(f) for f in temp_files],
                    chunks={'valid_time': max_hours},
                )
                with dask.config.set(scheduler='synchronous'):
                    combined.to_netcdf(output_path)
                combined.close()
            finally:
                # Cleanup temp files
                for f in temp_files:
                    if f.exists():
                        f.unlink()

        file_size_gb = output_path.stat().st_size / 1024**3
        print(f"    Saved: {file_size_gb:.2f} GB")

        return output_path

    def download_cell_period(
        self,
        bbox: "BoundingBox",
        cell_id: str,
        start_date: str,
        end_date: str,
        skip_existing: bool = True,
    ) -> Optional[Path]:
        """
        Download a time period of ERA5 10m wind data for a specific cell.

        Args:
            bbox: Bounding box for the cell
            cell_id: Identifier for the cell
            start_date: Start date in 'YYYY-MM-DD' format
            end_date: End date in 'YYYY-MM-DD' format
            skip_existing: Skip download if file already exists

        Returns:
            Path to downloaded file, or None if skipped/failed
        """
        output_path = self.get_cell_chunk_path(cell_id, start_date, end_date)

        if skip_existing and output_path.exists():
            print(f"    {start_date[:7]} already exists, skipping")
            return output_path

        print(f"    Fetching {start_date[:7]} to {end_date[:7]}...")

        ds = self._get_dataset()

        # Check if the requested dates are within the dataset's time range
        ds_start = str(ds.time.values[0])[:10]
        ds_end = str(ds.time.values[-1])[:10]

        if start_date < ds_start:
            print(f"      Warning: Requested start {start_date} is before dataset start {ds_start}")
            start_date = ds_start
        if end_date > ds_end:
            print(f"      Warning: Requested end {end_date} is after dataset end {ds_end}")
            end_date = ds_end

        # Convert bbox longitude from -180/180 to 0/360 system used by ARCO
        west_360 = bbox.west % 360 if bbox.west < 0 else bbox.west
        east_360 = bbox.east % 360 if bbox.east < 0 else bbox.east

        # Handle the case where the bbox crosses the antimeridian
        if west_360 > east_360:
            print(f"      Warning: Bbox crosses antimeridian, may need special handling")

        # Select time range and spatial extent
        # Note: ARCO latitude is DESCENDING (90 to -90), so slice north to south
        subset = ds.sel(
            time=slice(start_date, end_date),
            latitude=slice(bbox.north, bbox.south),  # Descending: north to south
            longitude=slice(west_360, east_360),
        )[[ARCO_VAR_U10, ARCO_VAR_V10]]

        # Print size info
        time_count = len(subset.time)
        lat_count = len(subset.latitude)
        lon_count = len(subset.longitude)
        estimated_mb = (time_count * lat_count * lon_count * 2 * 4) / 1024 / 1024
        print(f"      Sliced: {time_count} times x {lat_count} lat x {lon_count} lon (~{estimated_mb:.1f} MB)")

        # Rename variables and time coordinate to match expected format
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
        subset.load()  # Triggers actual download from GCS
        subset.to_netcdf(output_path)
        print(f"      Saved: {output_path.stat().st_size / 1024 / 1024:.1f} MB")
        subset.close()

        return output_path

    def download_period(
        self,
        start_date: str,
        end_date: str,
        skip_existing: bool = True,
    ) -> Optional[Path]:
        """
        Legacy method - not used for cell-based approach.
        Kept for API compatibility.
        """
        raise NotImplementedError("Use download_cell_period for cell-based downloads")

    def download_all_chunks(self, skip_existing: bool = True) -> List[Path]:
        """
        Download all ERA5 wind data in 6-month chunks.

        Args:
            skip_existing: Skip download if file already exists

        Returns:
            List of paths to downloaded NetCDF files
        """
        periods = self.get_chunk_periods()
        downloaded_files = []

        print(f"Downloading {len(periods)} periods ({ARCO_CHUNK_MONTHS}-month chunks)...")

        for i, (start_date, end_date) in enumerate(periods, 1):
            result = self.download_period(start_date, end_date, skip_existing)
            if result:
                downloaded_files.append(result)
            print(f"    [{i}/{len(periods)}] {start_date} to {end_date}: Done")

        return sorted(downloaded_files)

    def get_existing_chunk_files(self) -> List[Path]:
        """Get list of existing chunk files."""
        periods = self.get_chunk_periods()
        existing = []
        for start_date, end_date in periods:
            path = self.get_chunk_path(start_date, end_date)
            if path.exists():
                existing.append(path)
        return sorted(existing)

    def get_all_data_files(self, skip_existing: bool = True) -> List[Path]:
        """
        Get all data files, downloading if necessary.

        Args:
            skip_existing: Skip download if files already exist

        Returns:
            List of paths to NetCDF files
        """
        # Check if all files exist
        existing = self.get_existing_chunk_files()
        expected = len(self.get_chunk_periods())

        if len(existing) == expected and skip_existing:
            print(f"All {expected} chunk files already exist")
            return existing

        # Download missing files
        return self.download_all_chunks(skip_existing)

    # Legacy methods for backward compatibility with cell-based approach
    def download_for_cell(
        self,
        bbox,  # BoundingBox - ignored for global downloads
        cell_index: int,
        skip_existing: bool = True,
    ) -> List[Path]:
        """
        Legacy method for cell-based downloads.
        Now downloads global data (ignoring bbox) and returns all chunk files.

        Args:
            bbox: Ignored (kept for API compatibility)
            cell_index: Ignored (kept for API compatibility)
            skip_existing: Skip if file already exists

        Returns:
            List of paths to all NetCDF chunk files
        """
        return self.get_all_data_files(skip_existing)

    def get_existing_files_for_cell(self, cell_index: int) -> List[Path]:
        """
        Legacy method for cell-based file lookup.
        Returns all existing global chunk files.
        """
        return self.get_existing_chunk_files()

    def close(self):
        """Close the dataset if open."""
        if self._ds is not None:
            self._ds.close()
            self._ds = None
