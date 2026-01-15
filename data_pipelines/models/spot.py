"""Spot model for kite surfing locations."""
from attrs import define, field
from typing import Optional


@define
class Spot:
    """A kitesurfing spot with location data."""

    spot_id: str
    name: str
    latitude: float
    longitude: float
    country: Optional[str] = None

    @classmethod
    def from_dataframe_row(cls, row, spot_id: str, country: Optional[str] = None) -> "Spot":
        """Create a Spot from a pandas DataFrame row."""
        return cls(
            spot_id=spot_id,
            name=row["spotname"],
            latitude=row["lat"],
            longitude=row["long"],
            country=country,
        )
