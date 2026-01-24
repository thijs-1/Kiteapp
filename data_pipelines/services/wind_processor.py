"""Service for processing wind data from ERA5 NetCDF files."""
from pathlib import Path
from typing import Tuple, Dict, Optional, List
import numpy as np
import xarray as xr

from data_pipelines.config import MS_TO_KNOTS
from data_pipelines.models.spot import Spot
from data_pipelines.models.grid import BoundingBox


class WindProcessor:
    """Service for processing ERA5 wind data."""

    def __init__(self):
        """Initialize wind processor."""
        pass

    def calculate_wind_strength(self, u: np.ndarray, v: np.ndarray) -> np.ndarray:
        """
        Calculate wind strength in knots from u,v components.

        Args:
            u: East-west wind component (m/s)
            v: North-south wind component (m/s)

        Returns:
            Wind strength in knots
        """
        strength_ms = np.sqrt(u**2 + v**2)
        return strength_ms * MS_TO_KNOTS

    def calculate_wind_direction(self, u: np.ndarray, v: np.ndarray) -> np.ndarray:
        """
        Calculate wind direction in degrees (going-to direction).

        The direction indicates where the wind is going TO, not where it's
        coming FROM. 0° = North, 90° = East, 180° = South, 270° = West.

        Args:
            u: East-west wind component (m/s)
            v: North-south wind component (m/s)

        Returns:
            Wind direction in degrees [0, 360)
        """
        # atan2(u, v) gives the angle from north, clockwise
        # This is the "going to" direction
        direction = np.degrees(np.arctan2(u, v))
        # Normalize to [0, 360)
        direction = (direction + 360) % 360
        return direction

    def load_netcdf(self, nc_path: Path) -> xr.Dataset:
        """Load a NetCDF file."""
        return xr.open_dataset(nc_path)

    def load_netcdf_multi(self, nc_paths: list) -> xr.Dataset:
        """Load multiple NetCDF files as a single dataset."""
        return xr.open_mfdataset(
            nc_paths,
            combine="nested",
            concat_dim="valid_time",
            data_vars="minimal",
            coords="minimal",
            compat="override",
        )

    def find_nearest_point(
        self,
        ds: xr.Dataset,
        lat: float,
        lon: float,
    ) -> Tuple[int, int]:
        """
        Find the indices of the nearest grid point to given coordinates.

        Args:
            ds: xarray Dataset with latitude/longitude coordinates
            lat: Target latitude
            lon: Target longitude

        Returns:
            Tuple of (lat_idx, lon_idx)
        """
        # Get coordinate arrays
        lats = ds.latitude.values
        lons = ds.longitude.values

        # Find nearest indices
        lat_idx = int(np.abs(lats - lat).argmin())
        lon_idx = int(np.abs(lons - lon).argmin())

        return lat_idx, lon_idx

    def extract_spot_data(
        self,
        ds: xr.Dataset,
        spot: Spot,
    ) -> Dict[str, np.ndarray]:
        """
        Extract wind data for a specific spot from the dataset.

        Args:
            ds: xarray Dataset with ERA5 wind data
            spot: Spot to extract data for

        Returns:
            Dict with keys:
                - 'time': Array of timestamps
                - 'strength': Array of wind strength in knots
                - 'direction': Array of wind direction in degrees
        """
        # Find nearest grid point
        lat_idx, lon_idx = self.find_nearest_point(ds, spot.latitude, spot.longitude)

        # Extract u and v components at this point
        u = ds["u10"].isel(latitude=lat_idx, longitude=lon_idx).values
        v = ds["v10"].isel(latitude=lat_idx, longitude=lon_idx).values
        # Handle both 'time' and 'valid_time' coordinate names (CDS API uses valid_time)
        time = ds["valid_time"].values if "valid_time" in ds else ds["time"].values

        # Calculate strength and direction
        strength = self.calculate_wind_strength(u, v)
        direction = self.calculate_wind_direction(u, v)

        return {
            "time": time,
            "strength": strength,
            "direction": direction,
        }

    def process_netcdf_for_spot(
        self,
        nc_paths,
        spot: Spot,
    ) -> Optional[Dict[str, np.ndarray]]:
        """
        Process NetCDF file(s) to extract wind data for a spot.

        Args:
            nc_paths: Path to NetCDF file, or list of paths for multi-file dataset
            spot: Spot to process

        Returns:
            Wind data dict, or None if processing failed
        """
        try:
            if isinstance(nc_paths, (list, tuple)):
                ds = self.load_netcdf_multi(nc_paths)
            else:
                ds = self.load_netcdf(nc_paths)
            data = self.extract_spot_data(ds, spot)
            ds.close()
            return data
        except Exception as e:
            print(f"Error processing {nc_paths} for spot {spot.name}: {e}")
            return None

    def extract_cell_spots_data(
        self,
        ds: xr.Dataset,
        spots: List[Spot],
        bbox: BoundingBox,
    ) -> Dict[str, np.ndarray]:
        """
        Extract wind data for all spots in a cell using vectorized interpolation.

        This method provides significant performance improvement by:
        1. Subsetting the dataset to the cell's bounding box first (reduces memory)
        2. Using vectorized interpolation to extract all spots at once
        3. Using linear interpolation instead of nearest-neighbor

        Args:
            ds: xarray Dataset with ERA5 wind data (full globe or already subset)
            spots: List of spots to extract data for
            bbox: Bounding box for the cell (used to subset data)

        Returns:
            Dict with keys:
                - 'time': Array of timestamps (shape: num_times)
                - 'strength': Array of wind strength in knots (shape: num_times x num_spots)
                - 'direction': Array of wind direction in degrees (shape: num_times x num_spots)
        """
        # Subset to cell's bounding box FIRST (reduces memory)
        # Note: latitude may be in descending order in ERA5
        lat_min, lat_max = min(bbox.south, bbox.north), max(bbox.south, bbox.north)
        lon_min, lon_max = min(bbox.west, bbox.east), max(bbox.west, bbox.east)

        # Check latitude ordering in dataset
        lats = ds.latitude.values
        if lats[0] > lats[-1]:
            # Descending order (common in ERA5)
            cell_ds = ds.sel(
                latitude=slice(lat_max, lat_min),
                longitude=slice(lon_min, lon_max),
            )
        else:
            # Ascending order
            cell_ds = ds.sel(
                latitude=slice(lat_min, lat_max),
                longitude=slice(lon_min, lon_max),
            )

        # Build coordinate arrays for all spots
        spot_lats = xr.DataArray([s.latitude for s in spots], dims="spot")
        spot_lons = xr.DataArray([s.longitude for s in spots], dims="spot")

        # Vectorized interpolation - all spots in cell at once
        # This is much faster than looping through spots individually
        u_all = cell_ds["u10"].interp(
            latitude=spot_lats,
            longitude=spot_lons,
            method="linear",
        ).compute()

        v_all = cell_ds["v10"].interp(
            latitude=spot_lats,
            longitude=spot_lons,
            method="linear",
        ).compute()

        # Get time values
        time = cell_ds["valid_time"].values if "valid_time" in cell_ds else cell_ds["time"].values

        # Result shapes: (time, num_spots)
        u_values = u_all.values
        v_values = v_all.values

        strength = self.calculate_wind_strength(u_values, v_values)
        direction = self.calculate_wind_direction(u_values, v_values)

        return {
            "time": time,
            "strength": strength,   # shape: (num_times, num_spots)
            "direction": direction,  # shape: (num_times, num_spots)
        }
