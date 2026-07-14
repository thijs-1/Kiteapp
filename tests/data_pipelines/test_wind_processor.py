"""Tests for spot data extraction in WindProcessor."""
import numpy as np
import xarray as xr

from data_pipelines.models.spot import Spot
from data_pipelines.services.wind_processor import WindProcessor


def make_dataset() -> xr.Dataset:
    """2x2 grid with known corner values for interpolation checks."""
    time = np.array([np.datetime64("2024-06-21T12:00")])
    return xr.Dataset(
        {
            "u10": (("valid_time", "latitude", "longitude"), np.full((1, 2, 2), 5.0)),
            "v10": (("valid_time", "latitude", "longitude"), np.zeros((1, 2, 2))),
            # tp in meters: corners 1, 2, 3, 4 mm
            "tp": (
                ("valid_time", "latitude", "longitude"),
                np.array([[[0.001, 0.002], [0.003, 0.004]]]),
            ),
            # t2m in Kelvin: corners 10, 12, 14, 16 degrees C
            "t2m": (
                ("valid_time", "latitude", "longitude"),
                np.array([[[283.15, 285.15], [287.15, 289.15]]]),
            ),
        },
        coords={
            "valid_time": time,
            "latitude": [53.0, 52.75],
            "longitude": [4.75, 5.0],
        },
    )


def make_spot(lat: float, lon: float) -> Spot:
    return Spot(spot_id="s", name="s", latitude=lat, longitude=lon, country="NL")


class TestExtractSpotDataInterpolation:
    """Temperature and precipitation are interpolated to the spot location."""

    def test_weather_variables_interpolated_between_grid_points(self):
        ds = make_dataset()
        # Spot at the exact center of the 4 grid points -> bilinear mean
        spot = make_spot(52.875, 4.875)

        data = WindProcessor().extract_spot_data(ds, spot)

        assert data["precipitation"] == [2.5]
        assert data["temperature"] == [13.0]

    def test_spot_outside_grid_falls_back_to_nearest(self):
        ds = make_dataset()
        # Outside the coordinate range, where linear interpolation gives NaN
        spot = make_spot(54.0, 4.0)

        data = WindProcessor().extract_spot_data(ds, spot)

        assert data["precipitation"] == [1.0]
        assert data["temperature"] == [10.0]

    def test_missing_weather_variables_return_none(self):
        ds = make_dataset().drop_vars(["t2m", "tp"])
        spot = make_spot(52.875, 4.875)

        data = WindProcessor().extract_spot_data(ds, spot)

        assert data["temperature"] is None
        assert data["precipitation"] is None
        assert len(data["strength"]) == 1
