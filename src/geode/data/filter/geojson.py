import os
import json

from typing import Any

import shapely
from shapely.geometry import shape
from shapely.geometry.base import BaseGeometry
import xarray as xr

from geode.data.filter.base import OrFilter
from geode.data.filter.factory import register_filter
from geode.data.keys import LatitudeKey, LongitudeKey


@register_filter("geojson")
class GeoJsonFilter(OrFilter):
    def __init__(self, arg: dict[str, Any] | str):
        super().__init__(arg)

    def make_mask(self, ds: xr.DataTree):
        return self._mask_from_geometry(ds, self._make_geometry())

    def _make_geometry(self) -> BaseGeometry:
        """Build the shapely geometry described by the filter arguments.

        Subclasses override this hook to resolve geometries from other sources.
        """
        if isinstance(self.arg, str):
            return self._make_from_path(self.arg)
        return self._make_from_geojson_dict(self.arg)

    def _mask_from_geometry(self, ds: xr.DataTree, geometry: BaseGeometry):
        return shapely.intersects_xy(
            geometry,
            ds[LongitudeKey].values,
            ds[LatitudeKey].values,
        )

    def _make_from_path(self, path: str):
        try:
            # resolve the path to an absolute path and home directory ~
            path = os.path.expanduser(path)
            path = os.path.abspath(path)

            with open(path, "r") as f:
                geojson_data = json.load(f)
            return shape(geojson_data)
        except Exception as e:  # noqa: BLE001
            raise ValueError(f"Failed to load GeoJSON file at {path}: {e}")

        return shape(geojson_data)

    def _make_from_geojson_dict(self, geojson_dict: dict[str, Any]):
        try:
            return shape(geojson_dict)
        except Exception as e:  # noqa: BLE001
            raise ValueError(f"Failed to load GeoJSON data from dictionary: {e}")

    @classmethod
    def _validate(cls, arg: dict[str, Any] | str) -> None:
        if not isinstance(arg, dict) and not isinstance(arg, str):
            cls._validation_error(
                f"GeoJSON filter must be a string or dictionary, got {type(arg).__name__}."
            )

        if isinstance(arg, str):
            path = os.path.expanduser(arg)
            path = os.path.abspath(path)

            if not os.path.exists(path):
                cls._validation_error(f"GeoJSON file at path {path} does not exist.")

        if isinstance(arg, dict) and "type" not in arg:
            cls._validation_error(
                "Missing 'type' argument in GeoJSON dictionary. Must be a valid GeoJSON object."
            )
