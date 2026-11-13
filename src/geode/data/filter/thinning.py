"""Spatial thinning filter for GEODE observation DataTrees."""

from typing import Any
import numpy as np
import xarray as xr

from geode.data.filter.base import AndFilter
from geode.data.filter.distance_utils import cluster_by_distance_flat
from geode.data.filter.factory import register_filter
from geode.data.keys import LatitudeKey, LocationKey, LongitudeKey


@register_filter("thinning")
class ThinningFilter(AndFilter):
    """Subsamples observations along the Location dimension using grid or distance."""

    def __init__(self, arg: dict[str, Any]):
        super().__init__(arg)

    def apply(self, datatree: xr.DataTree) -> xr.DataTree:
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
            if isinstance(grid, (int, float)):
                dlat = dlon = float(grid)
            else:
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
    ) -> np.ndarray:
        sub_lats = lats[valid_indices]
        sub_lons = lons[valid_indices] % 360.0

        lat_bins = np.floor((sub_lats + 90.0) / dlat).astype(np.int64)
        lon_bins = np.floor(sub_lons / dlon).astype(np.int64)

        max_lon_bins = int(np.ceil(360.0 / dlon)) + 1
        cell_keys = lat_bins * max_lon_bins + lon_bins

        # Single O(N log N) sort with secondary tie-breaker key per strategy
        if strategy == "first":
            order = np.argsort(cell_keys, kind="stable")
        elif strategy == "random":
            rand_keys = np.random.default_rng(seed).random(len(cell_keys))
            order = np.lexsort((rand_keys, cell_keys))
        elif strategy == "center":
            center_lat = (lat_bins + 0.5) * dlat - 90.0
            center_lon = (lon_bins + 0.5) * dlon
            dist_sq = (sub_lats - center_lat) ** 2 + (sub_lons - center_lon) ** 2
            order = np.lexsort((dist_sq, cell_keys))
        else:
            raise ValueError(f"Invalid thinning strategy: {strategy}")

        sorted_cells = cell_keys[order]
        first_in_cell = np.r_[True, sorted_cells[1:] != sorted_cells[:-1]]
        return np.sort(valid_indices[order[first_in_cell]])

    @staticmethod
    def _thin_indices_distance(
        lats: np.ndarray,
        lons: np.ndarray,
        valid_indices: np.ndarray,
        distance_km: float,
        strategy: str,
        seed: int,
    ) -> np.ndarray:
        sub_lats = lats[valid_indices]
        sub_lons = lons[valid_indices]
        flat_indices, group_starts = cluster_by_distance_flat(
            sub_lats, sub_lons, distance_km=distance_km
        )
        if len(group_starts) == 0:
            return np.empty(0, dtype=np.int64)

        orig = valid_indices[flat_indices]
        counts = np.diff(np.append(group_starts, len(orig)))

        if strategy == "first":
            selected = orig[group_starts]
        elif strategy == "random":
            rng = np.random.default_rng(seed)
            offsets = rng.integers(0, counts)
            selected = orig[group_starts + offsets]
        elif strategy == "center":
            c_lats = sub_lats[flat_indices]
            c_lons = sub_lons[flat_indices]
            mean_lats = np.add.reduceat(c_lats, group_starts) / counts
            mean_lons = np.add.reduceat(c_lons, group_starts) / counts

            group_ids = np.repeat(np.arange(len(counts)), counts)
            dist_sq = (c_lats - mean_lats[group_ids]) ** 2 + (c_lons - mean_lons[group_ids]) ** 2
            order = np.lexsort((dist_sq, group_ids))
            selected = orig[order[group_starts]]
        else:
            raise ValueError(f"Invalid thinning strategy: {strategy}")

        return np.sort(selected)

    @classmethod
    def _validate(cls, arg: dict[str, Any]) -> None:
        if "grid" not in arg and "distance" not in arg:
            cls._validation_error("Thinning requires either 'grid' or 'distance' key.")
        if "grid" in arg and "distance" in arg:
            cls._validation_error("Specify either 'grid' or 'distance', not both.")
        if "strategy" in arg and arg["strategy"] not in ("center", "first", "random"):
            cls._validation_error(f"Invalid strategy: {arg['strategy']}")
