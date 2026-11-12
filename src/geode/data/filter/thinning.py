"""Spatial thinning filter for GEODE observation DataTrees."""

from typing import Any
import numpy as np
import xarray as xr

from geode.data.filter.base import AndFilter
from geode.data.filter.factory import register_filter
from geode.data.keys import LatitudeKey, LocationKey, LongitudeKey


@register_filter("thinning")
class ThinningFilter(AndFilter):
    """Subsamples observations along the Location dimension using grid or distance."""

    def __init__(self, arg: dict[str, Any]):
        super().__init__(arg)

    def apply(self, datatree: xr.DataTree) -> xr.DataTree:
        # Access latitude and longitude from DataTree (matches BoundingBoxFilter)
        lats = np.asarray(datatree[LatitudeKey].variable.values, dtype=np.float64)
        lons = np.asarray(datatree[LongitudeKey].variable.values, dtype=np.float64)

        valid_mask = np.isfinite(lats) & np.isfinite(lons)
        valid_indices = np.where(valid_mask)[0]
        if len(valid_indices) == 0:
            return datatree.map_over_datasets(
                lambda ds: ds.isel({LocationKey: []}) if LocationKey in ds.dims else ds
            )

        grid = self.arg.get("grid")
        distance = self.arg.get("distance")
        strategy = self.arg.get("strategy", "center")
        seed = self.arg.get("seed", 42)

        # 1. Grid-based thinning (dlat, dlon)
        if grid is not None:
            dlat, dlon = float(grid[0]), float(grid[1])
            selected = self._thin_indices_grid(
                lats, lons, valid_indices, dlat=dlat, dlon=dlon, strategy=strategy, seed=seed
            )
        # 2. Distance-based thinning (km or deg)
        elif distance is not None:
            units = self.arg.get("units", "km")
            distance_km = float(distance) * 111.195 if units == "deg" else float(distance)
            selected = self._thin_indices_distance(
                lats, lons, valid_indices, distance_km=distance_km, strategy=strategy, seed=seed
            )
        else:
            return datatree

        # Apply the selected indices across all groups containing the Location dimension
        return datatree.map_over_datasets(
            lambda ds: ds.isel({LocationKey: selected}) if LocationKey in ds.dims else ds
        )

    @staticmethod
    def _thin_indices_grid(
        lats: np.ndarray,
        lons: np.ndarray,
        valid_indices: np.ndarray,
        dlat: float,
        dlon: float,
        strategy: str,
        seed: int,
    ) -> list[int]:
        sub_lats = lats[valid_indices]
        sub_lons = lons[valid_indices] % 360.0

        lat_bins = np.floor((sub_lats + 90.0) / dlat).astype(np.int64)
        lon_bins = np.floor(sub_lons / dlon).astype(np.int64)

        max_lon_bins = int(np.ceil(360.0 / dlon)) + 1
        cell_keys = lat_bins * max_lon_bins + lon_bins

        rng = np.random.default_rng(seed)
        selected: list[int] = []
        unique_cells = np.unique(cell_keys)

        for cell in unique_cells:
            in_cell_mask = cell_keys == cell
            in_cell_locs = valid_indices[in_cell_mask]

            if strategy == "first":
                selected.append(int(in_cell_locs[0]))
            elif strategy == "random":
                selected.append(int(rng.choice(in_cell_locs)))
            elif strategy == "center":
                c_lat_idx = cell // max_lon_bins
                c_lon_idx = cell % max_lon_bins
                center_lat = (c_lat_idx + 0.5) * dlat - 90.0
                center_lon = (c_lon_idx + 0.5) * dlon

                cl_lats = lats[in_cell_locs]
                cl_lons = lons[in_cell_locs] % 360.0
                dist_sq = (cl_lats - center_lat) ** 2 + (cl_lons - center_lon) ** 2
                selected.append(int(in_cell_locs[np.argmin(dist_sq)]))

        selected.sort()
        return selected

    @staticmethod
    def _thin_indices_distance(
        lats: np.ndarray,
        lons: np.ndarray,
        valid_indices: np.ndarray,
        distance_km: float,
        strategy: str,
        seed: int,
    ) -> list[int]:
        from geode.data.filter.distance_utils import cluster_by_distance

        clusters = cluster_by_distance(
            lats[valid_indices],
            lons[valid_indices],
            distance_km=distance_km,
        )
        rng = np.random.default_rng(seed)
        selected: list[int] = []

        for cluster in clusters:
            orig = valid_indices[cluster]
            if strategy == "first":
                selected.append(int(orig[0]))
            elif strategy == "random":
                selected.append(int(rng.choice(orig)))
            elif strategy == "center":
                c_lats = lats[orig]
                c_lons = lons[orig]
                dist_sq = (c_lats - np.mean(c_lats)) ** 2 + (c_lons - np.mean(c_lons)) ** 2
                selected.append(int(orig[np.argmin(dist_sq)]))

        selected.sort()
        return selected

    @classmethod
    def _validate(cls, arg: dict[str, Any]) -> None:
        if "grid" not in arg and "distance" not in arg:
            cls._validation_error("Thinning requires either 'grid' or 'distance' key.")
        if "grid" in arg and "distance" in arg:
            cls._validation_error("Specify either 'grid' or 'distance', not both.")
        if "strategy" in arg and arg["strategy"] not in ("center", "first", "random"):
            cls._validation_error(f"Invalid strategy: {arg['strategy']}")
