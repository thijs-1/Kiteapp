"""Service for managing the geographic grid and spot assignments."""
from pathlib import Path
from typing import List
import pandas as pd

from data_pipelines.config import (
    ENRICHED_SPOTS_FILE,
    GRID_SIZE_LAT,
    GRID_SIZE_LON,
    GRID_EXPANSION_KM,
)
from data_pipelines.models.spot import Spot
from data_pipelines.models.grid import GridCell, BoundingBox
from data_pipelines.utils.file_utils import load_spots_dataframe
from data_pipelines.utils.geo_utils import (
    create_grid_cells,
    assign_spots_to_grid,
    get_cells_with_spots,
)


class GridService:
    """Service for managing geographic grid and spot assignments."""

    def __init__(self, spots_file: Path = ENRICHED_SPOTS_FILE):
        """Initialize with path to enriched spots file."""
        self.spots_file = spots_file
        self._spots: List[Spot] = []
        self._grid_cells: List[GridCell] = []
        self._loaded = False

    def load(self) -> None:
        """Load spots and assign to grid cells."""
        if self._loaded:
            return

        # Load spots from enriched file
        df = load_spots_dataframe(self.spots_file)
        self._spots = [
            Spot(
                spot_id=row["spot_id"],
                name=row["name"],
                latitude=float(row["latitude"]),
                longitude=float(row["longitude"]),
                country=row["country"],
            )
            for _, row in df.iterrows()
        ]

        # Create grid and assign spots
        self._grid_cells = create_grid_cells(GRID_SIZE_LAT, GRID_SIZE_LON)
        self._grid_cells = assign_spots_to_grid(self._spots, self._grid_cells)

        self._loaded = True

    @property
    def spots(self) -> List[Spot]:
        """Get all spots."""
        self.load()
        return self._spots

    @property
    def grid_cells(self) -> List[GridCell]:
        """Get all grid cells."""
        self.load()
        return self._grid_cells

    def get_cells_with_spots(self) -> List[GridCell]:
        """Get only grid cells that contain spots."""
        self.load()
        return get_cells_with_spots(self._grid_cells)

    def get_download_bbox(self, cell: GridCell) -> BoundingBox:
        """Get expanded bounding box for data download."""
        return cell.get_download_bbox(GRID_EXPANSION_KM)

    def get_cell_summary(self) -> dict:
        """Get summary statistics about the grid."""
        self.load()
        cells_with_spots = self.get_cells_with_spots()
        return {
            "total_spots": len(self._spots),
            "total_cells": len(self._grid_cells),
            "cells_with_spots": len(cells_with_spots),
            "spots_per_cell": {
                "min": min(len(c.spots) for c in cells_with_spots) if cells_with_spots else 0,
                "max": max(len(c.spots) for c in cells_with_spots) if cells_with_spots else 0,
                "avg": sum(len(c.spots) for c in cells_with_spots) / len(cells_with_spots) if cells_with_spots else 0,
            },
        }
