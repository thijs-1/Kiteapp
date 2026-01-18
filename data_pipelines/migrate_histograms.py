"""
Migrate old per-spot 1D histogram files to the new single 3D array format.

Run this once to convert existing data:
    python -m data_pipelines.migrate_histograms
"""
import pickle
from pathlib import Path
import numpy as np
from tqdm import tqdm

from data_pipelines.config import (
    PROCESSED_DATA_DIR,
    HISTOGRAMS_1D_FILE,
    WIND_BINS,
    DAYS_OF_YEAR,
)

# Old directory with per-spot files
OLD_HISTOGRAMS_1D_DIR = PROCESSED_DATA_DIR / "histograms_1d"


def migrate():
    """Convert old per-spot histogram files to single 3D array."""

    if not OLD_HISTOGRAMS_1D_DIR.exists():
        print(f"Old histogram directory not found: {OLD_HISTOGRAMS_1D_DIR}")
        return

    # Find all old histogram files
    old_files = list(OLD_HISTOGRAMS_1D_DIR.glob("*.pkl"))
    if not old_files:
        print("No old histogram files found.")
        return

    print(f"Found {len(old_files)} old histogram files to migrate...")

    # Create mappings
    day_to_idx = {day: idx for idx, day in enumerate(DAYS_OF_YEAR)}
    num_bins = len(WIND_BINS) - 1
    num_days = len(DAYS_OF_YEAR)

    # Accumulate data
    spot_ids = []
    histogram_data = []

    for file_path in tqdm(old_files, desc="Loading old files"):
        try:
            with open(file_path, "rb") as f:
                data = pickle.load(f)

            spot_id = data.get("spot_id") or file_path.stem
            daily_counts = data.get("daily_counts", {})

            # Convert to 2D array (num_days, num_bins)
            arr = np.zeros((num_days, num_bins), dtype=np.float32)
            for day, counts in daily_counts.items():
                if day in day_to_idx:
                    arr[day_to_idx[day]] = counts

            spot_ids.append(spot_id)
            histogram_data.append(arr)

        except Exception as e:
            print(f"Error loading {file_path}: {e}")
            continue

    if not spot_ids:
        print("No valid histogram data found.")
        return

    # Stack into 3D array
    data_3d = np.stack(histogram_data, axis=0)  # Shape: (num_spots, num_days, num_bins)

    print(f"Created 3D array with shape: {data_3d.shape}")

    # Save new format
    result = {
        "spot_ids": spot_ids,
        "bins": WIND_BINS,
        "days": DAYS_OF_YEAR,
        "data": data_3d,
    }

    HISTOGRAMS_1D_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(HISTOGRAMS_1D_FILE, "wb") as f:
        pickle.dump(result, f)

    print(f"Saved new format to: {HISTOGRAMS_1D_FILE}")
    print(f"  - {len(spot_ids)} spots")
    print(f"  - {num_days} days")
    print(f"  - {num_bins} wind bins")
    print(f"  - File size: {HISTOGRAMS_1D_FILE.stat().st_size / (1024*1024):.1f} MB")

    # Optionally remove old directory
    print(f"\nMigration complete! You can now delete the old directory:")
    print(f"  rmdir /s /q {OLD_HISTOGRAMS_1D_DIR}")


if __name__ == "__main__":
    migrate()
