import xarray as xr
from typing import Any
import json
import shapely
from shapely.geometry import shape

from geode.data.filter.apply import register_filter
from geode.data.filter.base import FilterBase


@register_filter("geojson")
class GeoJsonFilter(FilterBase):

    @classmethod
    def _make_mask(cls, ds: xr.DataTree, kwargs: dict[str, Any]):
        if "path" in kwargs:
            geom = cls._make_from_path(kwargs["path"])
        elif "type" in kwargs:
            geom = cls._make_from_geojson_dict(kwargs)

        return shapely.contains_xy(
            geom, 
            ds["MetaData/longitude"].values, 
            ds["MetaData/latitude"].values,
        )

    @classmethod
    def _make_from_path(cls, path: str):
        try:
            with open(path, "r") as f:
                geojson_data = json.load(f)
            return shape(geojson_data)
        except Exception as e:
            raise ValueError(f"Failed to load GeoJSON file at {path}: {e}")

        return shape(geojson_data)

    @classmethod
    def _make_from_geojson_dict(cls, geojson_dict: dict[str, Any]):
        try:
            return shape(geojson_dict)
        except Exception as e:
            raise ValueError(f"Failed to load GeoJSON data from dictionary: {e}")

    @classmethod
    def _validate(cls, kwargs: dict[str, Any]) -> None:
        if "path" in kwargs:
            pass
        elif "type" in kwargs:
            pass
        else:
            raise ValueError("Either 'path' or 'type' argument must be provided for the GeoJSON filter.")
