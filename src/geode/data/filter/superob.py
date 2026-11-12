"""Spatial superobbing filter for GEODE observation DataTrees."""

from typing import Any, Callable
import numpy as np
import xarray as xr

from geode.data.filter.base import AndFilter
from geode.data.filter.factory import register_filter
from geode.data.keys import LatitudeKey, LocationKey, LongitudeKey


@register_filter("superobbing")
@register_filter("superob")
class SuperobbingFilter(AndFilter):
    """Aggregates (superobs) observations along the Location dimension using grid or distance bins."""

    def __init__(self, arg: dict[str, Any]):
        super().__init__(arg)

    def apply(self, datatree: xr.DataTree) -> xr.DataTree:
        # Access latitude and longitude from DataTree (matches ThinningFilter)
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
        aggregation = self.arg.get("aggregation", self.arg.get("method", "mean"))
        min_obs = int(self.arg.get("min_obs", 1))

        # 1. Grid-based binning (dlat, dlon)
        if grid is not None:
            if isinstance(grid, (int, float)):
                dlat, dlon = float(grid), float(grid)
            else:
                dlat, dlon = float(grid[0]), float(grid[1])
            clusters = self._cluster_indices_grid(
                lats, lons, valid_indices, dlat=dlat, dlon=dlon, min_obs=min_obs
            )

        # 2. Distance-based clustering (km or deg)
        elif distance is not None:
            units = self.arg.get("units", "km")
            distance_km = float(distance) * 111.195 if units == "deg" else float(distance)
            clusters = self._cluster_indices_distance(
                lats, lons, valid_indices, distance_km=distance_km, min_obs=min_obs
            )
        else:
            return datatree

        if len(clusters) == 0:
            return datatree.map_over_datasets(
                lambda ds: ds.isel({LocationKey: []}) if LocationKey in ds.dims else ds
            )

        # Aggregate across all groups containing the Location dimension
        return datatree.map_over_datasets(
            lambda ds: self._aggregate_dataset(ds, clusters, aggregation=aggregation)
        )

    @staticmethod
    def _cluster_indices_grid(
        lats: np.ndarray,
        lons: np.ndarray,
        valid_indices: np.ndarray,
        dlat: float,
        dlon: float,
        min_obs: int = 1,
    ) -> list[np.ndarray]:
        sub_lats = lats[valid_indices]
        sub_lons = lons[valid_indices] % 360.0

        lat_bins = np.floor((sub_lats + 90.0) / dlat).astype(np.int64)
        lon_bins = np.floor(sub_lons / dlon).astype(np.int64)

        max_lon_bins = int(np.ceil(360.0 / dlon)) + 1
        cell_keys = lat_bins * max_lon_bins + lon_bins

        # Sort keys to split clusters in O(N log N)
        sort_order = np.argsort(cell_keys)
        sorted_cells = cell_keys[sort_order]
        sorted_valid = valid_indices[sort_order]

        split_idx = np.flatnonzero(np.diff(sorted_cells)) + 1
        cluster_groups = np.split(sorted_valid, split_idx)

        return [c for c in cluster_groups if len(c) >= min_obs]

    @staticmethod
    def _cluster_indices_distance(
        lats: np.ndarray,
        lons: np.ndarray,
        valid_indices: np.ndarray,
        distance_km: float,
        min_obs: int = 1,
    ) -> list[np.ndarray]:
        from geode.data.filter.distance_utils import cluster_by_distance

        raw_clusters = cluster_by_distance(
            lats[valid_indices],
            lons[valid_indices],
            distance_km=distance_km,
        )
        return [
            valid_indices[cluster]
            for cluster in raw_clusters
            if len(cluster) >= min_obs
        ]

    @classmethod
    def _aggregate_dataset(
        cls,
        ds: xr.Dataset,
        clusters: list[np.ndarray],
        aggregation: str = "mean",
    ) -> xr.Dataset:
        if LocationKey not in ds.dims:
            return ds

        new_data_vars = {}
        for var_name, da in ds.data_vars.items():
            if LocationKey not in da.dims:
                new_data_vars[var_name] = da
            else:
                new_data_vars[var_name] = cls._aggregate_variable(
                    da, clusters, aggregation=aggregation
                )

        new_coords = {}
        for coord_name, coord in ds.coords.items():
            if LocationKey not in coord.dims:
                new_coords[coord_name] = coord
            elif coord_name == LocationKey:
                new_coords[coord_name] = xr.DataArray(
                    np.arange(len(clusters), dtype=coord.dtype),
                    dims=[LocationKey],
                    attrs=coord.attrs,
                )
            else:
                new_coords[coord_name] = cls._aggregate_variable(
                    coord, clusters, aggregation=aggregation
                )

        return xr.Dataset(data_vars=new_data_vars, coords=new_coords, attrs=ds.attrs)

    @staticmethod
    def _aggregate_variable(
        da: xr.DataArray,
        clusters: list[np.ndarray],
        aggregation: str,
    ) -> xr.DataArray:
        loc_axis = da.get_axis_num(LocationKey)
        vals = da.values

        out_shape = list(vals.shape)
        out_shape[loc_axis] = len(clusters)
        out_indexer = [slice(None)] * vals.ndim
        indexer = [slice(None)] * vals.ndim

        # 1. Continuous physical variables (Radiance, BrightnessTemp, Lat, Lon)
        if np.issubdtype(vals.dtype, np.floating):
            agg_fn: Callable = np.nanmedian if aggregation == "median" else np.nanmean
            out_arr = np.empty(out_shape, dtype=vals.dtype)
            for i, c in enumerate(clusters):
                out_indexer[loc_axis] = i
                if len(c) == 1:
                    indexer[loc_axis] = c[0]
                    out_arr[tuple(out_indexer)] = vals[tuple(indexer)]
                else:
                    indexer[loc_axis] = c
                    sub = vals[tuple(indexer)]
                    with np.errstate(all="ignore"):
                        out_arr[tuple(out_indexer)] = agg_fn(sub, axis=loc_axis)

        # 2. Observation Timestamps
        elif np.issubdtype(vals.dtype, np.datetime64):
            out_arr = np.empty(out_shape, dtype=vals.dtype)
            for i, c in enumerate(clusters):
                out_indexer[loc_axis] = i
                indexer[loc_axis] = c
                sub = vals[tuple(indexer)]
                mean_int = np.int64(np.mean(sub.astype(np.int64)))
                out_arr[tuple(out_indexer)] = mean_int.astype(vals.dtype)

        # 3. Discrete variables (QC Flags, station IDs, indices, strings)
        else:
            out_arr = np.empty(out_shape, dtype=vals.dtype)
            for i, c in enumerate(clusters):
                out_indexer[loc_axis] = i
                indexer[loc_axis] = c[0]
                out_arr[tuple(out_indexer)] = vals[tuple(indexer)]

        return xr.DataArray(out_arr, dims=da.dims, attrs=da.attrs)

    @classmethod
    def _validate(cls, arg: dict[str, Any]) -> None:
        if "grid" not in arg and "distance" not in arg:
            cls._validation_error("Superobbing requires either 'grid' or 'distance' key.")
        if "grid" in arg and "distance" in arg:
            cls._validation_error("Specify either 'grid' or 'distance', not both.")
        agg = arg.get("aggregation", arg.get("method"))
        if agg is not None and agg not in ("mean", "median"):
            cls._validation_error(
                f"Invalid aggregation: '{agg}'. Must be 'mean' or 'median'."
            )
        if "min_obs" in arg and int(arg["min_obs"]) < 1:
            cls._validation_error("min_obs must be >= 1.")
