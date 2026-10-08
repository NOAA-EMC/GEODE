from typing import Any

import xarray as xr
import numpy as np

from geode.data.filter.apply import register_filter
from geode.data.filter.base import Filter, FilterType, ValidationError


LongitudeKey = "longitude"
LatitudeKey = "latitude"

@register_filter("bounding_box")
class BoundingBoxFilter(FilterType):

    @classmethod
    def validate(cls, args: dict[str, tuple[float, float]]) -> None:
        if not isinstance(args, dict):
            cls._validation_error("Arguments must be a dictionary with keys 'longitude' and 'latitude'.")
        if LongitudeKey not in args or LatitudeKey not in args:
            cls._validation_error("Arguments must contain 'longitude' and 'latitude' keys.")
        min_lon, max_lon = args[LongitudeKey]
        min_lat, max_lat = args[LatitudeKey]
        if not all(isinstance(arg, (int, float)) for arg in (min_lon, max_lon, min_lat, max_lat)):
            cls._validation_error("Arguments must be numeric instances.")

    @classmethod
    def make(cls, args: dict[str, tuple[float, float]]) -> Filter:
        min_lon, max_lon = args[LongitudeKey]
        min_lat, max_lat = args[LatitudeKey]
        return Filter(kind=Filter.Kind.Select, kwargs={LongitudeKey: slice(min_lon, max_lon), LatitudeKey: slice(min_lat, max_lat)})
