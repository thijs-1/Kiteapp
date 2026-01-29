"""
Main pipeline orchestrator for processing kite spot wind data.

This pipeline has two phases:

Phase 1 - Extract Time Series (chunk by chunk):
  1. Download one 6-month global ERA5 chunk (~36 GB)
  2. Extract wind time series for all spots → save to intermediate files
  3. Delete the global chunk
  4. Repeat for all chunks (20 total for 10 years)

Phase 2 - Build Histograms:
  1. Load complete 10-year time series per spot
  2. Build daily 1D and 2D histograms
  3. Save histograms
"""
from pathlib import Path
from typing import Optional, Dict, List
import numpy as np
import xarray as xr
from tqdm import tqdm

from data_pipelines.config import (
    CHECKPOINT_FILE,
    FILTER_DAYLIGHT_HOURS,
    HISTOGRAMS_1D_FILE,
    HISTOGRAMS_2D_DIR,
    RAW_DATA_DIR,
    TIMESERIES_DIR,
    WIND_BINS,
    DAYS_OF_YEAR,
)
from data_pipelines.services.grid_service import GridService
from data_pipelines.services.cds_service import CDSService
from data_pipelines.services.arco_service import ARCOService
from data_pipelines.services.wind_processor import WindProcessor
from data_pipelines.services.checkpoint_service import CheckpointService
from data_pipelines.services.histogram_builder import HistogramBuilder
from data_pipelines.services.timeseries_store import TimeseriesStore
from data_pipelines.utils.file_utils import save_pickle


class PipelineOrchestrator:
    """Orchestrates the wind data processing pipeline."""

    def __init__(
        self,
        skip_existing_downloads: bool = True,
        skip_existing_histograms: bool = True,
        cleanup_after_processing: bool = False,
        data_source: str = "cds",
    ):
        """
        Initialize the pipeline.

        Args:
            skip_existing_downloads: Skip downloading files that already exist
            skip_existing_histograms: Skip processing spots with existing histograms
            cleanup_after_processing: Delete raw NetCDF files after processing
            data_source: Data source to use ("arco" for Google Cloud, "cds" for Copernicus API)
        """
        self.grid_service = GridService()
        self.data_source = data_source
        if data_source == "arco":
            self.data_service = ARCOService()
            print("Using ARCO ERA5 (Google Cloud) - no queue wait times")
        else:
            self.data_service = CDSService()
            print("Using CDS API (Copernicus) - may have queue wait times")
        self.wind_processor = WindProcessor()
        self.histogram_builder = HistogramBuilder()
        self.timeseries_store = TimeseriesStore()

        self.skip_existing_downloads = skip_existing_downloads
        self.skip_existing_histograms = skip_existing_histograms
        self.cleanup_after_processing = cleanup_after_processing

        # Ensure output directories exist
        HISTOGRAMS_2D_DIR.mkdir(parents=True, exist_ok=True)
        HISTOGRAMS_1D_FILE.parent.mkdir(parents=True, exist_ok=True)
        TIMESERIES_DIR.mkdir(parents=True, exist_ok=True)

        # Accumulators for 1D histogram data
        self._histogram_1d_data: Dict[str, np.ndarray] = {}
        self._day_to_idx = {day: idx for idx, day in enumerate(DAYS_OF_YEAR)}
        self._num_bins = len(WIND_BINS) - 1

        # Spot coordinate lookup for daylight filtering
        # Built lazily on first access
        self._spot_coords: Optional[Dict[str, tuple]] = None

    def _get_spot_coords(self) -> Dict[str, tuple]:
        """
        Get spot coordinate lookup (spot_id -> (latitude, longitude)).

        Built lazily and cached for reuse.
        """
        if self._spot_coords is None:
            self._spot_coords = {}
            for spot in self.grid_service.spots:
                self._spot_coords[spot.spot_id] = (spot.latitude, spot.longitude)
            print(f"Built spot coordinate lookup: {len(self._spot_coords)} spots")
        return self._spot_coords

    # =========================================================================
    # Phase 1: Extract Time Series (cell-based, time-chunked)
    # =========================================================================

    def _extract_spots_from_dataset(
        self,
        ds: xr.Dataset,
        spots: List,
        bbox,
    ) -> Dict[str, Dict[str, np.ndarray]]:
        """
        Extract wind data for all spots from a dataset using vectorized interpolation.

        Returns:
            Dict mapping spot_id -> {'time', 'strength', 'direction'}
        """
        wind_data = self.wind_processor.extract_cell_spots_data(ds, spots, bbox)

        # Split vectorized result into per-spot dicts
        # Handle duplicate spot_ids by adding suffix for different locations
        result = {}
        seen_ids = {}  # spot_id -> count

        for i, spot in enumerate(spots):
            key = spot.spot_id
            if key in result:
                # Duplicate ID - add suffix
                seen_ids[key] = seen_ids.get(key, 1) + 1
                key = f"{spot.spot_id}_{seen_ids[key]}"

            result[key] = {
                "time": wind_data["time"],
                "strength": wind_data["strength"][:, i],
                "direction": wind_data["direction"][:, i],
            }
        return result

    def _process_cell_arco(
        self,
        cell_index: int,
        cell,
        periods: List[tuple],
    ) -> dict:
        """
        Process one cell: download all time chunks, extract time series, cleanup.

        Args:
            cell_index: Index of the cell
            cell: Cell object with spots
            periods: List of (start_date, end_date) tuples

        Returns:
            Dict with processing stats
        """
        cell_id = f"cell_{cell_index:04d}"
        bbox = self.grid_service.get_download_bbox(cell)
        spots = cell.spots

        stats = {
            "spots_processed": len(spots),
            "chunks_processed": 0,
            "bytes_freed": 0,
        }

        for start_date, end_date in periods:
            # Download this cell+time chunk
            chunk_path = self.data_service.download_cell_period(
                bbox, cell_id, start_date, end_date,
                skip_existing=self.skip_existing_downloads,
            )

            if not chunk_path or not chunk_path.exists():
                print(f"      Warning: Failed to download chunk")
                continue

            # Open and extract
            try:
                with xr.open_dataset(chunk_path) as ds:
                    spot_data = self._extract_spots_from_dataset(ds, spots, bbox)

                    # Append to time series store
                    for spot_id, data in spot_data.items():
                        self.timeseries_store.append_spot_data(
                            spot_id,
                            data["time"],
                            data["strength"],
                            data["direction"],
                        )

                stats["chunks_processed"] += 1

            except Exception as e:
                print(f"      Error extracting: {e}")
                import traceback
                traceback.print_exc()

            # Cleanup this chunk
            if self.cleanup_after_processing:
                try:
                    import gc
                    gc.collect()  # Help release file handles on Windows
                    size = chunk_path.stat().st_size
                    chunk_path.unlink()
                    stats["bytes_freed"] += size
                except PermissionError:
                    print(f"      Warning: Could not delete {chunk_path.name} (file locked)")
                except Exception as e:
                    print(f"      Warning: Cleanup error: {e}")

        return stats

    def run_phase1_arco(self, max_cells: Optional[int] = None, max_chunks: Optional[int] = None, test_days: Optional[int] = None) -> dict:
        """
        Phase 1: Download global chunks and extract time series (ARCO source).

        Downloads GLOBAL ERA5 data for each time period, extracts time series
        for ALL cells from that single file, then deletes and moves to next period.
        Uses checkpoint for resumability.

        Args:
            max_cells: Maximum number of cells to process (for testing)
            max_chunks: Maximum number of time chunks to process (for testing)
            test_days: Quick test mode with N days of data

        Returns:
            Dict with statistics
        """
        print("\n" + "=" * 60)
        print("PHASE 1: Extract Time Series from ARCO (Global Mode)")
        print("=" * 60)

        # Initialize checkpoint service
        checkpoint = CheckpointService(CHECKPOINT_FILE)
        state = checkpoint.load()

        # Get cells and spots
        cells_with_spots = self.grid_service.get_cells_with_spots()
        if max_cells:
            cells_with_spots = cells_with_spots[:max_cells]

        total_spots = sum(len(c.spots) for c in cells_with_spots)
        print(f"Cells: {len(cells_with_spots)}, Total spots: {total_spots}")

        # Get time periods (quarterly chunks)
        periods = self.data_service.get_chunk_periods(test_days=test_days)
        if max_chunks:
            periods = periods[:max_chunks]

        print(f"Time periods: {len(periods)} (3-month chunks)")
        print(f"Already completed: {len(state.completed_periods)} periods")
        if test_days:
            print(f"TEST MODE: {test_days} days only")
        if self.cleanup_after_processing:
            print("Cleanup enabled: global files deleted after extraction")

        stats = {
            "periods_total": len(periods),
            "periods_processed": 0,
            "periods_skipped": len(state.completed_periods),
            "cells_total": len(cells_with_spots),
            "spots_extracted": 0,
            "bytes_freed": 0,
        }

        for period_idx, (start_date, end_date) in enumerate(periods):
            period_key = f"{start_date}_{end_date}"

            # Skip completed periods
            if period_key in state.completed_periods:
                continue

            print(f"\n[{period_idx + 1}/{len(periods)}] Period: {start_date} to {end_date}")

            # Download GLOBAL chunk
            global_path = self.data_service.download_global_period(
                start_date, end_date,
                skip_existing=self.skip_existing_downloads,
            )

            if not global_path or not global_path.exists():
                print(f"  ERROR: Failed to download global chunk, skipping period")
                continue

            # Start checkpoint for this period
            checkpoint.start_period(period_key)

            # Extract all cells from the global file
            try:
                with xr.open_dataset(global_path) as ds:
                    for cell_idx, cell in enumerate(cells_with_spots):
                        # Skip cells already extracted (for resume)
                        if cell_idx in state.cells_extracted:
                            continue

                        bbox = self.grid_service.get_download_bbox(cell)
                        print(f"    Cell {cell_idx + 1}/{len(cells_with_spots)}: {len(cell.spots)} spots")

                        try:
                            spot_data = self._extract_spots_from_dataset(ds, cell.spots, bbox)

                            for spot_id, data in spot_data.items():
                                self.timeseries_store.append_spot_data(
                                    spot_id,
                                    data["time"],
                                    data["strength"],
                                    data["direction"],
                                )
                                stats["spots_extracted"] += 1

                            # Mark cell as extracted
                            checkpoint.mark_cell_extracted(cell_idx)
                            # Reload state to get updated cells_extracted
                            state = checkpoint.load()

                        except Exception as e:
                            print(f"      Error extracting cell {cell_idx}: {e}")
                            import traceback
                            traceback.print_exc()

            except Exception as e:
                print(f"  ERROR opening dataset: {e}")
                continue

            # Mark period complete
            checkpoint.complete_period()
            state = checkpoint.load()
            stats["periods_processed"] += 1

            # Cleanup global file
            if self.cleanup_after_processing:
                try:
                    import gc
                    gc.collect()  # Release file handles on Windows
                    size = global_path.stat().st_size
                    global_path.unlink()
                    stats["bytes_freed"] += size
                    print(f"  Cleaned up: {size / 1024**3:.2f} GB freed")
                except PermissionError:
                    print(f"  Warning: Could not delete {global_path.name} (file locked)")
                except Exception as e:
                    print(f"  Warning: Cleanup error: {e}")

        print(f"\nPhase 1 complete!")
        print(f"  Periods processed: {stats['periods_processed']}")
        print(f"  Periods skipped (already done): {stats['periods_skipped']}")
        print(f"  Time series size: {self.timeseries_store.get_total_size_mb():.1f} MB")
        if stats["bytes_freed"] > 0:
            print(f"  Disk freed: {stats['bytes_freed'] / 1024**3:.1f} GB")

        return stats

    # =========================================================================
    # Phase 2: Build Histograms
    # =========================================================================

    def histogram_2d_exists(self, spot_id: str) -> bool:
        """Check if 2D histogram file already exists for a spot."""
        return (HISTOGRAMS_2D_DIR / f"{spot_id}.pkl").exists()

    def save_histogram_2d(self, spot_id: str, hist_2d) -> None:
        """Save 2D histogram data to pickle file."""
        save_pickle(hist_2d.to_dict(), HISTOGRAMS_2D_DIR / f"{spot_id}.pkl")

    def add_histogram_1d(self, spot_id: str, hist_1d) -> None:
        """Add 1D histogram to accumulator."""
        arr = np.zeros((len(DAYS_OF_YEAR), self._num_bins), dtype=np.float32)
        for day, counts in hist_1d.daily_counts.items():
            if day in self._day_to_idx:
                arr[self._day_to_idx[day]] = counts
        self._histogram_1d_data[spot_id] = arr

    def save_all_1d_histograms(self) -> None:
        """Save all accumulated 1D histograms as a single 3D array."""
        if not self._histogram_1d_data:
            print("No 1D histogram data to save.")
            return

        spot_ids = list(self._histogram_1d_data.keys())
        num_spots = len(spot_ids)

        data = np.zeros((num_spots, len(DAYS_OF_YEAR), self._num_bins), dtype=np.float32)
        for i, spot_id in enumerate(spot_ids):
            data[i] = self._histogram_1d_data[spot_id]

        result = {
            "spot_ids": spot_ids,
            "bins": WIND_BINS,
            "days": DAYS_OF_YEAR,
            "data": data,
        }

        save_pickle(result, HISTOGRAMS_1D_FILE)
        print(f"Saved 1D histograms: {num_spots} spots x {len(DAYS_OF_YEAR)} days x {self._num_bins} bins")

    def load_existing_1d_histograms(self) -> None:
        """Load existing 1D histogram data if available."""
        if HISTOGRAMS_1D_FILE.exists() and self.skip_existing_histograms:
            import pickle
            with open(HISTOGRAMS_1D_FILE, "rb") as f:
                existing = pickle.load(f)
            for i, spot_id in enumerate(existing["spot_ids"]):
                self._histogram_1d_data[spot_id] = existing["data"][i]
            print(f"Loaded {len(self._histogram_1d_data)} existing 1D histograms")

    def run_phase2(self) -> dict:
        """
        Phase 2: Build histograms from extracted time series.

        Returns:
            Dict with statistics
        """
        print("\n" + "=" * 60)
        print("PHASE 2: Build Histograms from Time Series")
        print("=" * 60)

        # Load existing histograms if skipping
        self.load_existing_1d_histograms()

        spot_ids = self.timeseries_store.get_all_spot_ids()
        print(f"Found {len(spot_ids)} spots with time series data")

        # Get spot coordinates for daylight filtering
        if FILTER_DAYLIGHT_HOURS:
            spot_coords = self._get_spot_coords()
            print("Daylight filtering enabled: only including daytime hours in histograms")
        else:
            spot_coords = {}
            print("Daylight filtering disabled: including all hours")

        stats = {
            "spots_total": len(spot_ids),
            "spots_processed": 0,
            "spots_skipped": 0,
        }

        for spot_id in tqdm(spot_ids, desc="Building histograms"):
            # Check if already processed
            has_1d = spot_id in self._histogram_1d_data
            has_2d = self.histogram_2d_exists(spot_id)

            if self.skip_existing_histograms and has_1d and has_2d:
                stats["spots_skipped"] += 1
                continue

            # Load time series
            data = self.timeseries_store.load_spot_data(spot_id)
            if data is None:
                continue

            # Get spot coordinates for daylight filtering
            latitude, longitude = spot_coords.get(spot_id, (None, None))

            # Build histograms (with daylight filtering if coordinates available)
            hist_1d, hist_2d = self.histogram_builder.build_histograms(
                spot_id,
                data["time"],
                data["strength"],
                data["direction"],
                latitude=latitude,
                longitude=longitude,
            )

            # Save
            if not has_1d:
                self.add_histogram_1d(spot_id, hist_1d)
            if not has_2d:
                self.save_histogram_2d(spot_id, hist_2d)

            stats["spots_processed"] += 1

        # Save combined 1D histograms
        print("\nSaving combined 1D histogram data...")
        self.save_all_1d_histograms()

        print(f"\nPhase 2 complete!")
        print(f"  Spots processed: {stats['spots_processed']}")
        print(f"  Spots skipped: {stats['spots_skipped']}")

        return stats

    # =========================================================================
    # Legacy CDS flow (sequential, cell-based)
    # =========================================================================

    def run_cds(self, max_cells: Optional[int] = None) -> dict:
        """Run the legacy CDS pipeline (cell-based, sequential)."""
        print("Running legacy CDS pipeline...")

        cells_with_spots = self.grid_service.get_cells_with_spots()
        self.load_existing_1d_histograms()

        if max_cells:
            cells_with_spots = cells_with_spots[:max_cells]

        if FILTER_DAYLIGHT_HOURS:
            print("Daylight filtering enabled: only including daytime hours in histograms")
        else:
            print("Daylight filtering disabled: including all hours")

        stats = {
            "cells_processed": 0,
            "spots_processed": 0,
            "spots_skipped": 0,
        }

        for cell_index, cell in enumerate(tqdm(cells_with_spots)):
            download_bbox = self.grid_service.get_download_bbox(cell)
            nc_paths = self.data_service.download_for_cell(
                download_bbox, cell_index,
                skip_existing=self.skip_existing_downloads,
            )
            if not nc_paths:
                nc_paths = self.data_service.get_existing_files_for_cell(cell_index)
            if not nc_paths:
                continue

            for spot in cell.spots:
                has_1d = spot.spot_id in self._histogram_1d_data
                has_2d = self.histogram_2d_exists(spot.spot_id)

                if self.skip_existing_histograms and has_1d and has_2d:
                    stats["spots_skipped"] += 1
                    continue

                wind_data = self.wind_processor.process_netcdf_for_spot(nc_paths, spot)
                if wind_data is None:
                    continue

                # Pass spot coordinates for daylight filtering
                hist_1d, hist_2d = self.histogram_builder.build_histograms(
                    spot.spot_id,
                    wind_data["time"],
                    wind_data["strength"],
                    wind_data["direction"],
                    latitude=spot.latitude,
                    longitude=spot.longitude,
                )

                if not has_1d:
                    self.add_histogram_1d(spot.spot_id, hist_1d)
                if not has_2d:
                    self.save_histogram_2d(spot.spot_id, hist_2d)

                stats["spots_processed"] += 1

            stats["cells_processed"] += 1

            if self.cleanup_after_processing:
                cell_id = f"cell_{cell_index:04d}"
                for f in RAW_DATA_DIR.glob(f"era5_wind_{cell_id}_*.nc"):
                    f.unlink()

        self.save_all_1d_histograms()
        return stats

    # =========================================================================
    # Main entry point
    # =========================================================================

    def run(self, max_cells: Optional[int] = None, max_chunks: Optional[int] = None, test_days: Optional[int] = None) -> dict:
        """
        Run the full pipeline.

        Args:
            max_cells: Maximum cells to process (for testing)
            max_chunks: Maximum time chunks per cell for ARCO mode (for testing)
            test_days: Use only N days of data (for quick testing)

        Returns:
            Dict with overall statistics
        """
        print("Loading spots and building grid...")
        cells_with_spots = self.grid_service.get_cells_with_spots()
        total_spots = sum(len(c.spots) for c in cells_with_spots)
        print(f"Found {len(cells_with_spots)} grid cells with {total_spots} spots")

        if self.data_source == "arco":
            # Two-phase ARCO pipeline
            stats1 = self.run_phase1_arco(max_cells=max_cells, max_chunks=max_chunks, test_days=test_days)
            stats2 = self.run_phase2()
            return {**stats1, **stats2}
        else:
            # Legacy CDS pipeline
            return self.run_cds(max_cells=max_cells)


def main():
    """Run the data pipeline."""
    import argparse

    parser = argparse.ArgumentParser(description="Process kite spot wind data")
    parser.add_argument(
        "--max-cells",
        type=int,
        default=None,
        help="Maximum number of grid cells to process (CDS mode, for testing)",
    )
    parser.add_argument(
        "--max-chunks",
        type=int,
        default=None,
        help="Maximum number of time chunks to process (ARCO mode, for testing)",
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
        help="Delete raw NetCDF files after processing",
    )
    parser.add_argument(
        "--source",
        choices=["arco", "cds"],
        default="cds",
        help="Data source: 'cds' (Copernicus API, default) or 'arco' (Google Cloud)",
    )
    parser.add_argument(
        "--phase2-only",
        action="store_true",
        help="Skip phase 1, only build histograms from existing time series",
    )
    parser.add_argument(
        "--test-days",
        type=int,
        default=None,
        help="Quick test mode: use only N days of data (e.g., --test-days 2)",
    )
    parser.add_argument(
        "--clear-checkpoint",
        action="store_true",
        help="Clear checkpoint file and start fresh (ARCO mode)",
    )
    parser.add_argument(
        "--no-daylight-filter",
        action="store_true",
        help="Disable daylight filtering (include all 24 hours in histograms)",
    )

    args = parser.parse_args()

    # Override daylight filtering config if flag is set
    if args.no_daylight_filter:
        import data_pipelines.config as config
        config.FILTER_DAYLIGHT_HOURS = False

    # Clear checkpoint if requested
    if args.clear_checkpoint and args.source == "arco":
        checkpoint = CheckpointService(CHECKPOINT_FILE)
        checkpoint.clear()

    pipeline = PipelineOrchestrator(
        skip_existing_downloads=not args.force_download,
        skip_existing_histograms=not args.force_process,
        cleanup_after_processing=args.cleanup,
        data_source=args.source,
    )

    if args.phase2_only:
        pipeline.run_phase2()
    else:
        pipeline.run(max_cells=args.max_cells, max_chunks=args.max_chunks, test_days=args.test_days)


if __name__ == "__main__":
    main()
