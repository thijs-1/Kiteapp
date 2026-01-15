"""Geographic utility functions."""
import hashlib
from typing import List, Tuple
from data_pipelines.models.grid import BoundingBox, GridCell
from data_pipelines.models.spot import Spot


def generate_spot_id(spotname: str, lat: float, lon: float) -> str:
    """Generate a unique ID for a spot based on its name and coordinates."""
    # Ensure lat/lon are floats (may be strings in some DataFrames)
    lat_f = float(lat)
    lon_f = float(lon)
    data = f"{spotname}:{lat_f:.6f}:{lon_f:.6f}"
    return hashlib.md5(data.encode()).hexdigest()[:12]


def create_grid_cells(
    lat_size: float = 30.0,
    lon_size: float = 30.0,
) -> List[GridCell]:
    """
    Create grid cells covering the globe.

    Args:
        lat_size: Size of each cell in latitude degrees
        lon_size: Size of each cell in longitude degrees

    Returns:
        List of empty GridCell objects
    """
    cells = []

    # Latitude: -90 to 90
    lat = -90.0
    while lat < 90:
        north = min(lat + lat_size, 90)

        # Longitude: -180 to 180
        lon = -180.0
        while lon < 180:
            east = min(lon + lon_size, 180)

            bbox = BoundingBox(
                north=north,
                south=lat,
                east=east,
                west=lon,
            )
            cells.append(GridCell(bbox=bbox))

            lon = east
        lat = north

    return cells


def assign_spots_to_grid(
    spots: List[Spot],
    grid_cells: List[GridCell],
) -> List[GridCell]:
    """
    Assign spots to their corresponding grid cells.

    Args:
        spots: List of spots to assign
        grid_cells: List of grid cells

    Returns:
        Grid cells with spots assigned
    """
    for spot in spots:
        for cell in grid_cells:
            if cell.bbox.contains(spot.latitude, spot.longitude):
                cell.spots.append(spot)
                break

    return grid_cells


def get_cells_with_spots(grid_cells: List[GridCell]) -> List[GridCell]:
    """Filter to only grid cells that contain spots."""
    return [cell for cell in grid_cells if cell.has_spots]
