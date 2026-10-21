import json
from importlib.resources import files
from importlib.resources.abc import Traversable
from typing import Any

import shapely
import xarray as xr
from shapely.geometry.base import BaseGeometry

from geode.data.filter.apply import register_filter
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

    @classmethod
    def _make_geometry(cls, region: str) -> BaseGeometry:
        return cls._make_from_geojson_dict(cls.catalog.geojson(region))

    @classmethod
    def _validate(cls, region: Any) -> None:
        if not isinstance(region, str):
            cls._validation_error(
                f"Region must be a string naming one of {cls.catalog.names}, "
                f"got {type(region).__name__}."
            )
        if region not in cls.catalog:
            cls._validation_error(
                f"Unknown region '{region}'. Available regions: {cls.catalog.names}"
            )
