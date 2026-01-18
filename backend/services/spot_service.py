"""Service for spot filtering and statistics."""
from typing import List, Optional, Dict
import numpy as np
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
        # Get data from 3D array
        data = self.histogram_repo.get_1d_data()
        if data is None:
            return None

        idx = self.histogram_repo.get_spot_index(spot_id)
        if idx is None:
            return None

        # Get masks
        day_mask = self.histogram_repo.get_1d_day_indices(start_date, end_date)
        bin_mask = self.histogram_repo.get_1d_bin_mask(wind_min, wind_max)

        # Get spot data and apply masks
        spot_data = data[idx]  # Shape: (366, num_bins)
        filtered = spot_data[day_mask, :]  # Shape: (num_days_in_range, num_bins)

        total = filtered.sum()
        if total == 0:
            return None

        in_range = filtered[:, bin_mask].sum()
        return (in_range / total) * 100

    def _calculate_all_percentages_vectorized(
        self,
        wind_min: float,
        wind_max: float,
        start_date: str,
        end_date: str,
    ) -> Dict[str, float]:
        """
        Calculate kiteable percentage for ALL spots using vectorized operations.

        Returns:
            Dict mapping spot_id to percentage
        """
        data = self.histogram_repo.get_1d_data()
        if data is None:
            return {}

        spot_ids = self.histogram_repo.get_1d_spot_ids()
        if not spot_ids:
            return {}

        # Get masks
        day_mask = self.histogram_repo.get_1d_day_indices(start_date, end_date)
        bin_mask = self.histogram_repo.get_1d_bin_mask(wind_min, wind_max)

        # Apply day mask: data shape (num_spots, 366, num_bins) -> (num_spots, num_days, num_bins)
        filtered = data[:, day_mask, :]

        # Calculate totals per spot: sum over days and bins
        totals = filtered.sum(axis=(1, 2))  # Shape: (num_spots,)

        # Calculate in-range counts: sum over days, only selected bins
        in_range = filtered[:, :, bin_mask].sum(axis=(1, 2))  # Shape: (num_spots,)

        # Calculate percentages (avoid division by zero)
        with np.errstate(divide='ignore', invalid='ignore'):
            percentages = np.where(totals > 0, (in_range / totals) * 100, 0)

        # Build result dict
        return {spot_id: float(percentages[i]) for i, spot_id in enumerate(spot_ids)}

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
        Filter spots based on criteria using vectorized operations.

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

        # Calculate percentages for ALL spots at once (vectorized)
        all_percentages = self._calculate_all_percentages_vectorized(
            wind_min, wind_max, start_date, end_date
        )

        if not all_percentages:
            return []

        # Get spot metadata
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
            percentage = all_percentages.get(spot_id)

            if percentage is None or percentage < min_percentage:
                continue

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
