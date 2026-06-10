"""
Enrich spots with country data and nearest-airport driving distances.

This is a one-time preprocessing step that:
1. Loads the raw windguru_spots.pkl
2. Generates unique spot IDs
3. Adds country column via reverse geocoding
4. Adds nearest_airports column (driving distance to N nearest large airports)
5. Saves enriched data to data/processed/spots.pkl
"""
import argparse

import pandas as pd
import pycountry
import reverse_geocoder as rg

from data_pipelines.config import (
    AIRPORT_ROUTES_CACHE_FILE,
    AIRPORTS_REFERENCE_FILE,
    ENRICHED_SPOTS_FILE,
    INPUT_SPOTS_FILE,
    OSRM_RATE_LIMIT_SECONDS,
    OSRM_TABLE_URL,
    PROCESSED_DATA_DIR,
)
from data_pipelines.services.airport_service import AirportService
from data_pipelines.utils.file_utils import load_spots_dataframe, save_spots_dataframe
from data_pipelines.utils.geo_utils import generate_spot_id


def country_code_to_name(code: str) -> str:
    """Convert ISO 3166-1 alpha-2 country code to full country name."""
    try:
        country = pycountry.countries.get(alpha_2=code)
        if country:
            return country.name
    except (KeyError, LookupError):
        pass
    return code


def enrich_spots(
    max_spots: int = 0,
    skip_airports: bool = False,
    retry_failed: bool = False,
) -> pd.DataFrame:
    """Load spots and add country, spot_id, and nearest_airports columns."""
    print(f"Loading spots from {INPUT_SPOTS_FILE}...")
    df = load_spots_dataframe(INPUT_SPOTS_FILE)
    print(f"Loaded {len(df)} spots")

    if max_spots and max_spots > 0:
        df = df.head(max_spots).copy()
        print(f"Limited to first {len(df)} spots (--max-spots)")

    print("Generating spot IDs...")
    df["spot_id"] = df.apply(
        lambda row: generate_spot_id(row["spotname"], row["lat"], row["long"]),
        axis=1,
    )

    coordinates = list(zip(df["lat"], df["long"]))
    print(f"Reverse geocoding {len(coordinates)} coordinates...")
    results = rg.search(coordinates)
    df["country"] = [country_code_to_name(r["cc"]) for r in results]

    df = df.rename(columns={"spotname": "name", "lat": "latitude", "long": "longitude"})
    df = df[["spot_id", "name", "latitude", "longitude", "country"]]

    if skip_airports:
        df["nearest_airports"] = [[] for _ in range(len(df))]
    else:
        print(f"\nComputing nearest airports via OSRM ({OSRM_TABLE_URL})...")
        service = AirportService(
            airports_csv=AIRPORTS_REFERENCE_FILE,
            cache_path=AIRPORT_ROUTES_CACHE_FILE,
            osrm_table_url=OSRM_TABLE_URL,
            rate_limit_seconds=OSRM_RATE_LIMIT_SECONDS,
            retry_failed=retry_failed,
        )
        df["nearest_airports"] = service.compute_for_dataframe(df)

    df = df[["spot_id", "name", "latitude", "longitude", "country", "nearest_airports"]]

    print(f"\nFound spots in {df['country'].nunique()} countries")
    print("Top 10 countries by spot count:")
    print(df["country"].value_counts().head(10))

    if not skip_airports:
        airport_counts = df["nearest_airports"].apply(len)
        print(
            f"\nAirport coverage: "
            f"{(airport_counts == 3).sum()} spots with 3 airports, "
            f"{(airport_counts.between(1, 2)).sum()} with 1-2, "
            f"{(airport_counts == 0).sum()} with none"
        )

    return df


def main():
    """Run the spot enrichment process."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--max-spots",
        type=int,
        default=0,
        help="Process only the first N spots (0 = all). Useful for dry runs.",
    )
    parser.add_argument(
        "--skip-airports",
        action="store_true",
        help="Skip the airport-distance enrichment step.",
    )
    parser.add_argument(
        "--retry-failed",
        action="store_true",
        help="Drop null entries from the route cache and retry them.",
    )
    args = parser.parse_args()

    PROCESSED_DATA_DIR.mkdir(parents=True, exist_ok=True)

    df = enrich_spots(
        max_spots=args.max_spots,
        skip_airports=args.skip_airports,
        retry_failed=args.retry_failed,
    )

    print(f"\nSaving enriched spots to {ENRICHED_SPOTS_FILE}...")
    save_spots_dataframe(df, ENRICHED_SPOTS_FILE)
    print("Done!")

    return df


if __name__ == "__main__":
    main()
