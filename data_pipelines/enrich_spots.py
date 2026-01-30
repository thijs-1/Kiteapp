"""
Enrich spots with country data using reverse geocoding.

This is a one-time preprocessing step that:
1. Loads the raw windguru_spots.pkl
2. Adds country column via reverse geocoding
3. Generates unique spot IDs
4. Saves enriched data to data/processed/spots.pkl
"""
import pandas as pd
import pycountry
import reverse_geocoder as rg
from tqdm import tqdm


def country_code_to_name(code: str) -> str:
    """Convert ISO 3166-1 alpha-2 country code to full country name."""
    try:
        country = pycountry.countries.get(alpha_2=code)
        if country:
            return country.name
    except (KeyError, LookupError):
        pass
    # Return the code if no match found
    return code

from data_pipelines.config import INPUT_SPOTS_FILE, ENRICHED_SPOTS_FILE, PROCESSED_DATA_DIR
from data_pipelines.utils.file_utils import load_spots_dataframe, save_spots_dataframe
from data_pipelines.utils.geo_utils import generate_spot_id


def enrich_spots() -> pd.DataFrame:
    """Load spots and add country and spot_id columns."""
    print(f"Loading spots from {INPUT_SPOTS_FILE}...")
    df = load_spots_dataframe(INPUT_SPOTS_FILE)
    print(f"Loaded {len(df)} spots")

    # Generate spot IDs
    print("Generating spot IDs...")
    df["spot_id"] = df.apply(
        lambda row: generate_spot_id(row["spotname"], row["lat"], row["long"]),
        axis=1,
    )

    # Prepare coordinates for reverse geocoding
    coordinates = list(zip(df["lat"], df["long"]))

    print(f"Reverse geocoding {len(coordinates)} coordinates...")
    # reverse_geocoder does batch lookup efficiently
    results = rg.search(coordinates)

    # Extract country codes and convert to full names
    df["country"] = [country_code_to_name(r["cc"]) for r in results]

    # Rename columns for consistency
    df = df.rename(columns={"spotname": "name", "lat": "latitude", "long": "longitude"})

    # Reorder columns
    df = df[["spot_id", "name", "latitude", "longitude", "country"]]

    print(f"Found spots in {df['country'].nunique()} countries")
    print("\nTop 10 countries by spot count:")
    print(df["country"].value_counts().head(10))

    return df


def main():
    """Run the spot enrichment process."""
    # Ensure output directory exists
    PROCESSED_DATA_DIR.mkdir(parents=True, exist_ok=True)

    # Enrich spots
    df = enrich_spots()

    # Save enriched data
    print(f"\nSaving enriched spots to {ENRICHED_SPOTS_FILE}...")
    save_spots_dataframe(df, ENRICHED_SPOTS_FILE)
    print("Done!")

    return df


if __name__ == "__main__":
    main()
