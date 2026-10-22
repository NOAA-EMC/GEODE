import json
from importlib.resources import files
from importlib.resources.abc import Traversable
from typing import Any

import shapely
import xarray as xr
from shapely.geometry import shape
from shapely.geometry.base import BaseGeometry

from geode.data.filter.factory import register_filter
from geode.data.filter.geojson import GeoJsonFilter

RegionFileSuffix = ".geojson"


class RegionCatalog:
    def __init__(self, directory: Traversable):
        self._directory = directory
        self._geojson_cache: dict[str, dict[str, Any]] = {}

    @property
    def names(self) -> list[str]:
        """Sorted list of available region names."""
        return sorted(
            entry.name.removesuffix(RegionFileSuffix)
            for entry in self._directory.iterdir()
            if entry.is_file() and entry.name.endswith(RegionFileSuffix)
        )

    def __contains__(self, name: object) -> bool:
        return isinstance(name, str) and self.normalize(name) in self.names

    @staticmethod
    def normalize(name: str) -> str:
        return name.strip().lower()

    def geojson(self, name: str) -> dict[str, Any]:
        key = self.normalize(name)
        if key not in self.names:
            raise KeyError(f"Unknown region '{name}'. Available regions: {self.names}")
        if key not in self._geojson_cache:
            region_file = self._directory / f"{key}{RegionFileSuffix}"
            self._geojson_cache[key] = json.loads(region_file.read_text())
        return self._geojson_cache[key]


region_catalog = RegionCatalog(files(__package__) / "regions")


@register_filter("region")
class RegionFilter(GeoJsonFilter):
    catalog: RegionCatalog = region_catalog

    def __init__(self, kwargs: str | dict[str, Any]):
        super().__init__(kwargs)

    def _make_geometry(self) -> BaseGeometry:
        if isinstance(self.kwargs, str):
            self.kwargs = {"name": self.kwargs}

        geometry = shape(self.catalog.geojson(self.kwargs["name"]))

        if "border_width" in self.kwargs:
            geometry = geometry.buffer(self.kwargs["border_width"])

        return geometry

    @classmethod
    def _validate(cls, args: str | dict[str, Any]) -> None:
        if not isinstance(args, str) and not isinstance(args, dict):
            cls._validation_error(
                f"Region must be a string naming one of {cls.catalog.names}, "
                f"got {type(args).__name__}."
            )
        if isinstance(args, str):
            if args not in cls.catalog:
                cls._validation_error(
                    f"Unknown region '{args}'. Available regions: {cls.catalog.names}"
                )
        elif isinstance(args, dict):
            if "name" not in args:
                cls._validation_error(
                    f"Region dictionary must have a 'name' key. Available regions: {cls.catalog.names}"
                )
            if args["name"] not in cls.catalog:
                cls._validation_error(
                    f"Unknown region '{args['name']}'. Available regions: {cls.catalog.names}"
                )
