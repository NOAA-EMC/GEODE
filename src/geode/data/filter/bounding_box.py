from typing import Any

import xarray as xr
import numpy as np

from geode.data.filter.apply import register_filter
from geode.data.filter.base import FilterBase


LongitudeKey = "MetaData/longitude"
LatitudeKey = "MetaData/latitude"

@register_filter("bounding_box")
class BoundingBoxFilter(FilterBase):

    @classmethod
    def _make_mask(cls, ds: xr.DataTree, kwargs: dict[str, Any]):
        min_lat = kwargs["min_lat"]
        max_lat = kwargs["max_lat"]
        min_lon = kwargs["min_lon"]
        max_lon = kwargs["max_lon"]
        lat = ds[LatitudeKey].variable
        lon = ds[LongitudeKey].variable
        return ((lat >= min_lat) & (lat <= max_lat) & (lon >= min_lon) & (lon <= max_lon)).values

    @classmethod
    def _validate(cls, kwargs: dict[str, Any]) -> None:
        required_keys = ["min_lat", "max_lat", "min_lon", "max_lon"]
        for key in required_keys:
            if key not in kwargs:
                raise ValueError(f"Missing required keyword argument: {key}")
        if kwargs["min_lat"] > kwargs["max_lat"]:
            raise ValueError("min_lat cannot be greater than max_lat")
        if kwargs["min_lon"] > kwargs["max_lon"]:
            raise ValueError("min_lon cannot be greater than max_lon")
