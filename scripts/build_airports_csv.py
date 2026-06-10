"""Build data/airports.csv from the OurAirports dataset.

Downloads the full OurAirports dump (~85K rows) and writes the pre-filtered
reference CSV used by the airport enrichment pipeline:

- type is large_airport or medium_airport
- scheduled_service is "yes" (commercial flights actually land there)
- non-empty IATA code and valid coordinates

Kite destinations are frequently served by medium airports with scheduled
service (Sal, Zanzibar, Jericoacoara, ...), so filtering to large_airport
only would report the nearest hub hundreds of km away instead.

Usage:
    python -m scripts.build_airports_csv [--url URL] [--output PATH]
"""
import argparse
import io
from pathlib import Path

import pandas as pd
import requests

DEFAULT_URL = (
    "https://raw.githubusercontent.com/davidmegginson/ourairports-data/main/airports.csv"
)
DEFAULT_OUTPUT = Path(__file__).resolve().parent.parent / "data" / "airports.csv"

KEPT_TYPES = ("large_airport", "medium_airport")
OUTPUT_COLUMNS = [
    "type",
    "name",
    "iata_code",
    "iso_country",
    "municipality",
    "latitude_deg",
    "longitude_deg",
]


def build_airports_csv(url: str = DEFAULT_URL, output: Path = DEFAULT_OUTPUT) -> pd.DataFrame:
    """Download the OurAirports dump, filter it, and write the reference CSV."""
    print(f"Downloading {url}...")
    resp = requests.get(url, timeout=60)
    resp.raise_for_status()
    df = pd.read_csv(io.StringIO(resp.text))
    print(f"Downloaded {len(df)} airports")

    iata = df["iata_code"].astype("string").str.strip()
    mask = (
        df["type"].isin(KEPT_TYPES)
        & (df["scheduled_service"] == "yes")
        & iata.notna()
        & (iata != "")
        & df["latitude_deg"].between(-90, 90)
        & df["longitude_deg"].between(-180, 180)
    )
    filtered = df.loc[mask, OUTPUT_COLUMNS].copy()
    filtered["iata_code"] = filtered["iata_code"].str.strip()
    filtered = filtered.sort_values("iata_code").reset_index(drop=True)

    print(f"Kept {len(filtered)} airports "
          f"({(filtered['type'] == 'large_airport').sum()} large, "
          f"{(filtered['type'] == 'medium_airport').sum()} medium)")

    output.parent.mkdir(parents=True, exist_ok=True)
    filtered.to_csv(output, index=False)
    print(f"Wrote {output}")
    return filtered


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url", default=DEFAULT_URL, help="OurAirports airports.csv URL")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT, help="Output CSV path")
    args = parser.parse_args()
    build_airports_csv(url=args.url, output=args.output)


if __name__ == "__main__":
    main()
