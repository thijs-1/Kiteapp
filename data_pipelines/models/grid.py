"""Grid and bounding box models for geographic operations."""
from attrs import define, field
from typing import List
from .spot import Spot


@define
class BoundingBox:
    """Geographic bounding box defined by coordinates."""

    north: float  # Max latitude
    south: float  # Min latitude
    east: float   # Max longitude
    west: float   # Min longitude

    def contains(self, lat: float, lon: float) -> bool:
        """Check if a point is within this bounding box."""
        return (self.south <= lat <= self.north and
                self.west <= lon <= self.east)

    def expand_by_km(self, km: float) -> "BoundingBox":
        """Expand the bounding box by a given number of kilometers."""
        # Approximate: 1 degree latitude ≈ 111 km
        # Longitude varies with latitude, use average
        lat_delta = km / 111.0
        avg_lat = (self.north + self.south) / 2
        lon_delta = km / (111.0 * abs(cos_deg(avg_lat)))

        return BoundingBox(
            north=min(90, self.north + lat_delta),
            south=max(-90, self.south - lat_delta),
            east=min(180, self.east + lon_delta),
            west=max(-180, self.west - lon_delta),
        )

    def expand_by_degrees(self, degrees: float) -> "BoundingBox":
        """Expand the bounding box by a given number of degrees."""
        return BoundingBox(
            north=min(90, self.north + degrees),
            south=max(-90, self.south - degrees),
            east=min(180, self.east + degrees),
            west=max(-180, self.west - degrees),
        )

    def to_cds_area(self) -> List[float]:
        """Convert to CDS API area format: [north, west, south, east]."""
        return [self.north, self.west, self.south, self.east]


@define
class GridCell:
    """A grid cell containing kite spots."""

    bbox: BoundingBox
    spots: List[Spot] = field(factory=list)

    @property
    def has_spots(self) -> bool:
        """Check if this grid cell contains any spots."""
        return len(self.spots) > 0

    def get_download_bbox(self, expansion_degrees: float) -> BoundingBox:
        """Get expanded bounding box for data download."""
        return self.bbox.expand_by_degrees(expansion_degrees)


def cos_deg(degrees: float) -> float:
    """Cosine of angle in degrees."""
    import math
    return math.cos(math.radians(degrees))
