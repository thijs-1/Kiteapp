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
    """Daily histogram of maximum sustained wind strength as percentages.

    For each day of year, stores the percentage of days (across all years)
    that had max sustained wind in each bin. To get "% of days with sustained
    wind >= X knots", sum the percentages from bin X onwards.
    """

    spot_id: str
    sustained_hours: int  # Minimum consecutive hours required
    bins: list  # Wind strength bin edges (same as 1D histogram)
    # Dict mapping day-of-year ("01-01", ...) to percentage per bin (sums to 100)
    daily_percentages: Dict[str, np.ndarray]

    def to_dict(self) -> dict:
        """Convert to serializable dictionary."""
        return {
            "spot_id": self.spot_id,
            "sustained_hours": self.sustained_hours,
            "bins": self.bins,
            "daily_percentages": {k: v.tolist() for k, v in self.daily_percentages.items()},
        }
