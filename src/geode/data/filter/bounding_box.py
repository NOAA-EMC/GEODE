from typing import Any

import xarray as xr
import numpy as np

from geode.data.filter.factory import register_filter
from geode.data.filter.base import OrFilter
from geode.data.keys import LatitudeKey, LongitudeKey


@register_filter("bounding_box")
class BoundingBoxFilter(OrFilter):
    def __init__(self, arg: dict[str, Any]):
        super().__init__(arg)

    def make_mask(self, ds: xr.DataTree):
        min_lat = self.arg["min_lat"]
        max_lat = self.arg["max_lat"]
        min_lon = self.arg["min_lon"]
        max_lon = self.arg["max_lon"]
        lat = ds[LatitudeKey].variable
        lon = ds[LongitudeKey].variable
        
        return (
            (lat >= min_lat) & (lat <= max_lat) & (lon >= min_lon) & (lon <= max_lon)
        ).values

    @classmethod
    def _validate(cls, arg: dict[str, Any]) -> None:
        required_keys = ["min_lat", "max_lat", "min_lon", "max_lon"]
        for key in required_keys:
            if key not in arg:
                cls._validation_error(f"Missing required keyword argument: {key}")
        if arg["min_lat"] > arg["max_lat"]:
            cls._validation_error("min_lat cannot be greater than max_lat")
        if arg["min_lon"] > arg["max_lon"]:
            cls._validation_error("min_lon cannot be greater than max_lon")
