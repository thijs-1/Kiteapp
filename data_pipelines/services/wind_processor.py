"""Service for processing wind data from ERA5 NetCDF files."""
from pathlib import Path
from typing import Tuple, Dict, Optional
import numpy as np
import xarray as xr

from data_pipelines.config import MS_TO_KNOTS
from data_pipelines.models.spot import Spot


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
        time = ds["time"].values

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
        nc_path: Path,
        spot: Spot,
    ) -> Optional[Dict[str, np.ndarray]]:
        """
        Process a NetCDF file to extract wind data for a spot.

        Args:
            nc_path: Path to NetCDF file
            spot: Spot to process

        Returns:
            Wind data dict, or None if processing failed
        """
        try:
            ds = self.load_netcdf(nc_path)
            data = self.extract_spot_data(ds, spot)
            ds.close()
            return data
        except Exception as e:
            print(f"Error processing {nc_path} for spot {spot.name}: {e}")
            return None
