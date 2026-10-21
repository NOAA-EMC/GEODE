import xarray as xr
from typing import Any
import json
import shapely
from shapely.geometry import shape
from shapely.geometry.base import BaseGeometry

from geode.data.filter.factory import register_filter
from geode.data.filter.base import FilterBase


@register_filter("geojson")
class GeoJsonFilter(FilterBase):
    def __init__(self, kwargs: dict[str, Any]):
        super().__init__(kwargs)

    def make_mask(self, ds: xr.DataTree):
        return self._mask_from_geometry(ds, self._make_geometry())

    def _make_geometry(self) -> BaseGeometry:
        """Build the shapely geometry described by the filter arguments.

        Subclasses override this hook to resolve geometries from other sources.
        """
        if "path" in self.kwargs:
            return self._make_from_path(self.kwargs["path"])
        return self._make_from_geojson_dict(self.kwargs)

    def _mask_from_geometry(self, ds: xr.DataTree, geometry: BaseGeometry):
        return shapely.intersects_xy(
            geometry,
            ds["MetaData/longitude"].values,
            ds["MetaData/latitude"].values,
        )

    def _make_from_path(self, path: str):
        try:
            with open(path, "r") as f:
                geojson_data = json.load(f)
            return shape(geojson_data)
        except Exception as e:
            raise ValueError(f"Failed to load GeoJSON file at {path}: {e}")

        return shape(geojson_data)

    def _make_from_geojson_dict(self, geojson_dict: dict[str, Any]):
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
            cls._validation_error(
                "Either 'path' or 'type' argument must be provided for the GeoJSON filter."
            )
