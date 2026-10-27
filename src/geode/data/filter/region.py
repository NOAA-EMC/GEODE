import json
from importlib.resources import files
from importlib.resources.abc import Traversable
from typing import Any

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

    def __init__(self, arg: str | dict[str, Any]):
        super().__init__(arg)

    def _make_geometry(self) -> BaseGeometry:
        if isinstance(self.arg, str):
            self.arg = {"name": self.arg}

        geometry = shape(self.catalog.geojson(self.arg["name"]))

        if "border_width" in self.arg:
            geometry = geometry.buffer(self.arg["border_width"])

        return geometry

    @classmethod
    def _validate(cls, arg: str | dict[str, Any]) -> None:
        if not isinstance(arg, str) and not isinstance(arg, dict):
            cls._validation_error(
                f"Region must be a string naming one of {cls.catalog.names}, "
                f"got {type(arg).__name__}."
            )
        if isinstance(arg, str):
            if arg not in cls.catalog:
                cls._validation_error(
                    f"Unknown region '{arg}'. Available regions: {cls.catalog.names}"
                )
        elif isinstance(arg, dict):
            if "name" not in arg:
                cls._validation_error(
                    f"Region dictionary must have a 'name' key. Available regions: {cls.catalog.names}"
                )
            if arg["name"] not in cls.catalog:
                cls._validation_error(
                    f"Unknown region '{arg['name']}'. Available regions: {cls.catalog.names}"
                )
