"""Utilities for working with meteorological winds."""

import numpy as np


def wind_components(
    wind_direction: float | None, wind_speed: float | None
) -> tuple[float | None, float | None]:
    """Convert meteorological wind direction and speed to east/north components.

    Parameters
    ----------
    wind_direction : float | None
        Direction the wind comes from, in degrees clockwise from north.
    wind_speed : float | None
        Wind speed in metres per second.

    Returns
    -------
    tuple[float | None, float | None]
        Eastward U and northward V components in metres per second.

    Examples
    --------
    A 10 m/s wind from west returns ``(10.0, 0.0)``.
    """
    if wind_speed is None:
        return None, None
    if wind_direction is None:
        if wind_speed == 0.0:
            return 0.0, 0.0
        return None, None

    direction_radians = np.deg2rad(wind_direction)
    eastward_wind = -wind_speed * np.sin(direction_radians)
    northward_wind = -wind_speed * np.cos(direction_radians)
    return float(eastward_wind), float(northward_wind)
