"""Service for spot filtering and statistics."""
from typing import List, Optional
import pandas as pd

from backend.data.spot_repository import SpotRepository
from backend.data.histogram_repository import HistogramRepository
from backend.schemas.spot import SpotBase, SpotWithStats


class SpotService:
    """Service for spot operations."""

    def __init__(
        self,
        spot_repo: SpotRepository = None,
        histogram_repo: HistogramRepository = None,
    ):
        """Initialize service with repositories."""
        self.spot_repo = spot_repo or SpotRepository()
        self.histogram_repo = histogram_repo or HistogramRepository()

    def get_all_spots(self) -> List[SpotBase]:
        """Get all spots as SpotBase objects."""
        df = self.spot_repo.get_all_spots()
        return [
            SpotBase(
                spot_id=row["spot_id"],
                name=row["name"],
                latitude=row["latitude"],
                longitude=row["longitude"],
                country=row["country"],
            )
            for _, row in df.iterrows()
        ]

    def get_spot(self, spot_id: str) -> Optional[SpotBase]:
        """Get a single spot by ID."""
        row = self.spot_repo.get_spot_by_id(spot_id)
        if row is None:
            return None
        return SpotBase(
            spot_id=row["spot_id"],
            name=row["name"],
            latitude=row["latitude"],
            longitude=row["longitude"],
            country=row["country"],
        )

    def calculate_kiteable_percentage(
        self,
        spot_id: str,
        wind_min: float,
        wind_max: float,
        start_date: str,
        end_date: str,
    ) -> Optional[float]:
        """
        Calculate the percentage of time wind is within the specified range.

        Args:
            spot_id: Spot ID
            wind_min: Minimum wind speed in knots
            wind_max: Maximum wind speed in knots
            start_date: Start date (MM-DD)
            end_date: End date (MM-DD)

        Returns:
            Percentage of time wind is in range, or None if no data
        """
        hist_data = self.histogram_repo.get_1d_histogram(spot_id)
        if not hist_data:
            return None

        bins = hist_data["bins"]
        daily_counts = hist_data["daily_counts"]

        # Filter to date range
        filtered_dates = self._filter_dates(list(daily_counts.keys()), start_date, end_date)
        if not filtered_dates:
            return None

        total_in_range = 0
        total_count = 0

        for date in filtered_dates:
            counts = daily_counts.get(date, [])
            if not counts:
                continue

            for i, count in enumerate(counts):
                bin_low = bins[i]
                bin_high = bins[i + 1] if i + 1 < len(bins) else float("inf")

                total_count += count

                # Check if bin overlaps with desired range
                if bin_low >= wind_min and bin_high <= wind_max:
                    total_in_range += count
                elif bin_low < wind_max and bin_high > wind_min:
                    # Partial overlap - count it
                    total_in_range += count

        if total_count == 0:
            return None

        return (total_in_range / total_count) * 100

    def _filter_dates(
        self,
        dates: List[str],
        start_date: str,
        end_date: str,
    ) -> List[str]:
        """Filter dates to those within the specified range."""
        # Handle year wrap-around (e.g., Nov 1 to Feb 28)
        if start_date <= end_date:
            # Normal range within same year
            return [d for d in dates if start_date <= d <= end_date]
        else:
            # Wraps around year end
            return [d for d in dates if d >= start_date or d <= end_date]

    def filter_spots(
        self,
        wind_min: float = 0,
        wind_max: float = 100,
        start_date: str = "01-01",
        end_date: str = "12-31",
        country: Optional[str] = None,
        name: Optional[str] = None,
        min_percentage: float = 75,
    ) -> List[SpotWithStats]:
        """
        Filter spots based on criteria.

        Args:
            wind_min: Minimum wind speed in knots
            wind_max: Maximum wind speed in knots (100 = infinity)
            start_date: Start date (MM-DD)
            end_date: End date (MM-DD)
            country: Filter by country code
            name: Filter by spot name (substring)
            min_percentage: Minimum kiteable percentage

        Returns:
            List of spots meeting criteria with their statistics
        """
        # Convert wind_max of 100 to infinity
        if wind_max >= 100:
            wind_max = float("inf")

        # Start with all spots or filtered by country/name
        if country:
            df = self.spot_repo.filter_by_country(country)
        elif name:
            df = self.spot_repo.search_by_name(name)
        else:
            df = self.spot_repo.get_all_spots()

        if name and country:
            # Apply name filter on top of country filter
            df = df[df["name"].str.lower().str.contains(name.lower(), na=False)]

        results = []

        for _, row in df.iterrows():
            spot_id = row["spot_id"]

            # Calculate kiteable percentage
            percentage = self.calculate_kiteable_percentage(
                spot_id, wind_min, wind_max, start_date, end_date
            )

            if percentage is None:
                continue

            if percentage >= min_percentage:
                results.append(
                    SpotWithStats(
                        spot_id=spot_id,
                        name=row["name"],
                        latitude=row["latitude"],
                        longitude=row["longitude"],
                        country=row["country"],
                        kiteable_percentage=round(percentage, 1),
                    )
                )

        # Sort by kiteable percentage descending
        results.sort(key=lambda x: x.kiteable_percentage, reverse=True)

        return results

    def get_countries(self) -> List[str]:
        """Get list of all countries."""
        return self.spot_repo.get_countries()
