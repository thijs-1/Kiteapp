"""Histogram data structures for wind data."""
from attrs import define
from typing import Dict
import numpy as np


@define
class DailyHistogram1D:
    """Daily 1D histogram of wind strength."""

    spot_id: str
    bins: list  # Wind strength bin edges
    # Dict mapping day-of-year ("01-01", "01-02", ...) to histogram counts
    daily_counts: Dict[str, np.ndarray]

    def to_dict(self) -> dict:
        """Convert to serializable dictionary."""
        return {
            "spot_id": self.spot_id,
            "bins": self.bins,
            "daily_counts": {k: v.tolist() for k, v in self.daily_counts.items()},
        }


@define
class DailyHistogram2D:
    """Daily 2D histogram of wind strength and direction."""

    spot_id: str
    strength_bins: list  # Wind strength bin edges
    direction_bins: list  # Wind direction bin edges
    # Dict mapping day-of-year to 2D histogram array (strength x direction)
    daily_counts: Dict[str, np.ndarray]

    def to_dict(self) -> dict:
        """Convert to serializable dictionary."""
        return {
            "spot_id": self.spot_id,
            "strength_bins": self.strength_bins,
            "direction_bins": self.direction_bins,
            "daily_counts": {k: v.tolist() for k, v in self.daily_counts.items()},
        }


@define
class DailySustainedWind:
    """Daily maximum wind strength sustained for a minimum duration.

    Records the maximum wind strength that was maintained for at least
    `sustained_hours` consecutive hours, aggregated by day of year.
    """

    spot_id: str
    sustained_hours: int  # Minimum consecutive hours required
    # Dict mapping day-of-year ("01-01", ...) to max sustained wind strength (knots)
    daily_max_sustained: Dict[str, float]

    def to_dict(self) -> dict:
        """Convert to serializable dictionary."""
        return {
            "spot_id": self.spot_id,
            "sustained_hours": self.sustained_hours,
            "daily_max_sustained": self.daily_max_sustained,
        }
