"""
Main pipeline orchestrator for processing kite spot wind data.

This pipeline:
1. Loads enriched spots from data/processed/spots.pkl
2. Divides globe into 30x30 degree grid cells
3. For each cell with spots:
   a. Downloads 10 years of ERA5 wind data from CDS
   b. Processes wind data for each spot in the cell
   c. Builds and saves daily 1D and 2D histograms
   d. Optionally deletes raw data to save disk space
"""
from pathlib import Path
from typing import Optional
from tqdm import tqdm

from data_pipelines.config import (
    HISTOGRAMS_1D_DIR,
    HISTOGRAMS_2D_DIR,
    RAW_DATA_DIR,
)
from data_pipelines.services.grid_service import GridService
from data_pipelines.services.cds_service import CDSService
from data_pipelines.services.wind_processor import WindProcessor
from data_pipelines.services.histogram_builder import HistogramBuilder
from data_pipelines.utils.file_utils import save_pickle


class PipelineOrchestrator:
    """Orchestrates the wind data processing pipeline."""

    def __init__(
        self,
        skip_existing_downloads: bool = True,
        skip_existing_histograms: bool = True,
        cleanup_after_processing: bool = False,
    ):
        """
        Initialize the pipeline.

        Args:
            skip_existing_downloads: Skip downloading files that already exist
            skip_existing_histograms: Skip processing spots with existing histograms
            cleanup_after_processing: Delete raw NetCDF files after processing each cell
        """
        self.grid_service = GridService()
        self.cds_service = CDSService()
        self.wind_processor = WindProcessor()
        self.histogram_builder = HistogramBuilder()

        self.skip_existing_downloads = skip_existing_downloads
        self.skip_existing_histograms = skip_existing_histograms
        self.cleanup_after_processing = cleanup_after_processing

        # Ensure output directories exist
        HISTOGRAMS_1D_DIR.mkdir(parents=True, exist_ok=True)
        HISTOGRAMS_2D_DIR.mkdir(parents=True, exist_ok=True)

    def histogram_exists(self, spot_id: str) -> bool:
        """Check if histogram files already exist for a spot."""
        h1d_path = HISTOGRAMS_1D_DIR / f"{spot_id}.pkl"
        h2d_path = HISTOGRAMS_2D_DIR / f"{spot_id}.pkl"
        return h1d_path.exists() and h2d_path.exists()

    def save_histograms(self, spot_id: str, hist_1d, hist_2d) -> None:
        """Save histogram data to pickle files."""
        h1d_path = HISTOGRAMS_1D_DIR / f"{spot_id}.pkl"
        h2d_path = HISTOGRAMS_2D_DIR / f"{spot_id}.pkl"

        save_pickle(hist_1d.to_dict(), h1d_path)
        save_pickle(hist_2d.to_dict(), h2d_path)

    def cleanup_cell_data(self, cell_index: int) -> int:
        """
        Delete raw NetCDF files for a cell.

        Returns:
            Number of bytes freed
        """
        cell_id = f"cell_{cell_index:04d}"
        bytes_freed = 0

        # Delete combined file
        combined_path = RAW_DATA_DIR / f"era5_wind_{cell_id}.nc"
        if combined_path.exists():
            bytes_freed += combined_path.stat().st_size
            combined_path.unlink()
            print(f"  Deleted: {combined_path.name}")

        # Delete yearly files
        for yearly_file in RAW_DATA_DIR.glob(f"era5_wind_{cell_id}_*.nc"):
            bytes_freed += yearly_file.stat().st_size
            yearly_file.unlink()
            print(f"  Deleted: {yearly_file.name}")

        return bytes_freed

    def all_spots_processed(self, cell) -> bool:
        """Check if all spots in a cell already have histograms."""
        for spot in cell.spots:
            if not self.histogram_exists(spot.spot_id):
                return False
        return True

    def process_cell(self, cell_index: int, cell) -> dict:
        """
        Process a single grid cell.

        Returns:
            Dict with processing statistics
        """
        stats = {
            "spots_total": len(cell.spots),
            "spots_processed": 0,
            "spots_skipped": 0,
            "download_skipped": False,
            "bytes_freed": 0,
            "cell_skipped": False,
        }

        # Skip entire cell if all spots already have histograms
        if self.skip_existing_histograms and self.all_spots_processed(cell):
            stats["spots_skipped"] = len(cell.spots)
            stats["cell_skipped"] = True
            return stats

        # Get expanded bounding box for download
        download_bbox = self.grid_service.get_download_bbox(cell)

        # Download ERA5 data for this cell
        nc_path = self.cds_service.download_for_cell(
            download_bbox,
            cell_index,
            skip_existing=self.skip_existing_downloads,
        )

        if nc_path is None:
            # File already existed
            stats["download_skipped"] = True
            cell_id = f"cell_{cell_index:04d}"
            nc_path = RAW_DATA_DIR / f"era5_wind_{cell_id}.nc"

        if not nc_path.exists():
            print(f"Warning: NetCDF file not found for cell {cell_index}")
            return stats

        # Process each spot in the cell
        for spot in cell.spots:
            # Skip if histograms already exist
            if self.skip_existing_histograms and self.histogram_exists(spot.spot_id):
                stats["spots_skipped"] += 1
                continue

            # Extract wind data for this spot
            wind_data = self.wind_processor.process_netcdf_for_spot(nc_path, spot)

            if wind_data is None:
                continue

            # Build histograms
            hist_1d, hist_2d = self.histogram_builder.build_histograms(
                spot.spot_id,
                wind_data["time"],
                wind_data["strength"],
                wind_data["direction"],
            )

            # Save histograms
            self.save_histograms(spot.spot_id, hist_1d, hist_2d)
            stats["spots_processed"] += 1

        # Cleanup raw data if requested
        if self.cleanup_after_processing:
            stats["bytes_freed"] = self.cleanup_cell_data(cell_index)

        return stats

    def run(self, max_cells: Optional[int] = None) -> dict:
        """
        Run the full pipeline.

        Args:
            max_cells: Maximum number of cells to process (for testing)

        Returns:
            Dict with overall statistics
        """
        print("Loading spots and building grid...")
        cells_with_spots = self.grid_service.get_cells_with_spots()

        if max_cells:
            cells_with_spots = cells_with_spots[:max_cells]

        total_stats = {
            "cells_total": len(cells_with_spots),
            "cells_processed": 0,
            "cells_skipped": 0,
            "spots_processed": 0,
            "spots_skipped": 0,
            "downloads_skipped": 0,
            "bytes_freed": 0,
        }

        print(f"Processing {len(cells_with_spots)} grid cells...")
        if self.cleanup_after_processing:
            print("Cleanup enabled: raw data will be deleted after processing each cell")

        for cell_index, cell in enumerate(tqdm(cells_with_spots)):
            cell_stats = self.process_cell(cell_index, cell)

            total_stats["cells_processed"] += 1
            total_stats["spots_processed"] += cell_stats["spots_processed"]
            total_stats["spots_skipped"] += cell_stats["spots_skipped"]
            total_stats["bytes_freed"] += cell_stats["bytes_freed"]
            if cell_stats.get("cell_skipped"):
                total_stats["cells_skipped"] += 1
            if cell_stats["download_skipped"]:
                total_stats["downloads_skipped"] += 1

        print("\nPipeline complete!")
        print(f"  Cells processed: {total_stats['cells_processed']}")
        print(f"  Cells skipped (already done): {total_stats['cells_skipped']}")
        print(f"  Spots processed: {total_stats['spots_processed']}")
        print(f"  Spots skipped: {total_stats['spots_skipped']}")
        print(f"  Downloads skipped: {total_stats['downloads_skipped']}")
        if total_stats["bytes_freed"] > 0:
            gb_freed = total_stats["bytes_freed"] / (1024 ** 3)
            print(f"  Disk space freed: {gb_freed:.2f} GB")

        return total_stats


def main():
    """Run the data pipeline."""
    import argparse

    parser = argparse.ArgumentParser(description="Process kite spot wind data")
    parser.add_argument(
        "--max-cells",
        type=int,
        default=None,
        help="Maximum number of grid cells to process (for testing)",
    )
    parser.add_argument(
        "--force-download",
        action="store_true",
        help="Re-download files even if they exist",
    )
    parser.add_argument(
        "--force-process",
        action="store_true",
        help="Re-process spots even if histograms exist",
    )
    parser.add_argument(
        "--cleanup",
        action="store_true",
        help="Delete raw NetCDF files after processing each cell (saves ~3GB per cell)",
    )

    args = parser.parse_args()

    pipeline = PipelineOrchestrator(
        skip_existing_downloads=not args.force_download,
        skip_existing_histograms=not args.force_process,
        cleanup_after_processing=args.cleanup,
    )

    pipeline.run(max_cells=args.max_cells)


if __name__ == "__main__":
    main()
