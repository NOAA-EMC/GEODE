"""Spatial superobbing filter for GEODE observation DataTrees."""

from typing import Any
import numpy as np
import xarray as xr

from geode.data.filter.base import AndFilter
from geode.data.filter.distance_utils import cluster_by_distance_flat
from geode.data.filter.factory import register_filter
from geode.data.keys import LatitudeKey, LocationKey, LongitudeKey


@register_filter("superobbing")
@register_filter("superob")
class SuperobbingFilter(AndFilter):
    """Aggregates (superobs) observations along the Location dimension using grid or distance bins."""

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
        aggregation = self.arg.get("aggregation", self.arg.get("method", "mean"))
        min_obs = int(self.arg.get("min_obs", 1))

        # 1. Grid-based binning (dlat, dlon)
        if grid is not None:
            if isinstance(grid, (int, float)):
                dlat, dlon = float(grid), float(grid)
            else:
                dlat, dlon = float(grid[0]), float(grid[1])
            kept_indices, group_starts = self._cluster_indices_grid(
                lats, lons, valid_indices, dlat=dlat, dlon=dlon, min_obs=min_obs
            )

        # 2. Distance-based clustering (km or deg)
        elif distance is not None:
            units = self.arg.get("units", "km")
            distance_km = float(distance) * 111.195 if units == "deg" else float(distance)
            kept_indices, group_starts = self._cluster_indices_distance(
                lats, lons, valid_indices, distance_km=distance_km, min_obs=min_obs
            )
        else:
            return datatree

        if len(group_starts) == 0:
            return datatree.map_over_datasets(
                lambda ds: ds.isel({LocationKey: []}) if LocationKey in ds.dims else ds
            )

        return datatree.map_over_datasets(
            lambda ds: self._aggregate_dataset(
                ds, kept_indices, group_starts, aggregation=aggregation
            )
        )

    @staticmethod
    def _filter_min_obs(
        flat_indices: np.ndarray,
        group_starts: np.ndarray,
        min_obs: int,
    ) -> tuple[np.ndarray, np.ndarray]:
        """Vectorized filtering of CSR cluster arrays by minimum observation count."""
        if len(group_starts) == 0 or min_obs <= 1:
            return flat_indices, group_starts

        counts = np.diff(np.append(group_starts, len(flat_indices)))
        valid_groups = counts >= min_obs
        if not np.any(valid_groups):
            return np.empty(0, dtype=np.int64), np.empty(0, dtype=np.int64)

        valid_counts = counts[valid_groups]
        new_starts = np.empty(len(valid_counts), dtype=np.int64)
        new_starts[0] = 0
        np.cumsum(valid_counts[:-1], out=new_starts[1:])

        old_starts = group_starts[valid_groups]
        group_ids = np.repeat(np.arange(len(valid_counts)), valid_counts)
        intra_offsets = np.arange(len(group_ids)) - new_starts[group_ids]
        kept_indices = flat_indices[old_starts[group_ids] + intra_offsets]
        return kept_indices, new_starts

    @classmethod
    def _cluster_indices_grid(
        cls,
        lats: np.ndarray,
        lons: np.ndarray,
        valid_indices: np.ndarray,
        dlat: float,
        dlon: float,
        min_obs: int = 1,
    ) -> tuple[np.ndarray, np.ndarray]:
        sub_lats = lats[valid_indices]
        sub_lons = lons[valid_indices] % 360.0

        lat_bins = np.floor((sub_lats + 90.0) / dlat).astype(np.int64)
        lon_bins = np.floor(sub_lons / dlon).astype(np.int64)

        max_lon_bins = int(np.ceil(360.0 / dlon)) + 1
        cell_keys = lat_bins * max_lon_bins + lon_bins

        sort_order = np.argsort(cell_keys)
        sorted_cells = cell_keys[sort_order]
        sorted_valid = valid_indices[sort_order]

        group_starts = np.r_[0, np.flatnonzero(sorted_cells[1:] != sorted_cells[:-1]) + 1]
        return cls._filter_min_obs(sorted_valid, group_starts, min_obs)

    @classmethod
    def _cluster_indices_distance(
        cls,
        lats: np.ndarray,
        lons: np.ndarray,
        valid_indices: np.ndarray,
        distance_km: float,
        min_obs: int = 1,
    ) -> tuple[np.ndarray, np.ndarray]:
        raw_flat, group_starts = cluster_by_distance_flat(
            lats[valid_indices],
            lons[valid_indices],
            distance_km=distance_km,
        )
        if len(group_starts) == 0:
            return np.empty(0, dtype=np.int64), np.empty(0, dtype=np.int64)

        mapped_flat = valid_indices[raw_flat]
        return cls._filter_min_obs(mapped_flat, group_starts, min_obs)

    @classmethod
    def _aggregate_dataset(
        cls,
        ds: xr.Dataset,
        kept_indices: np.ndarray,
        group_starts: np.ndarray,
        aggregation: str = "mean",
    ) -> xr.Dataset:
        if LocationKey not in ds.dims:
            return ds

        n_clusters = len(group_starts)
        first_obs_indices = kept_indices[group_starts]

        new_data_vars = {}
        for var_name, da in ds.data_vars.items():
            if LocationKey not in da.dims:
                new_data_vars[var_name] = da
            else:
                new_data_vars[var_name] = cls._aggregate_variable(
                    da,
                    kept_indices=kept_indices,
                    group_starts=group_starts,
                    first_obs_indices=first_obs_indices,
                    aggregation=aggregation,
                    is_longitude=(var_name == LongitudeKey),
                )

        new_coords = {}
        for coord_name, coord in ds.coords.items():
            if LocationKey not in coord.dims:
                new_coords[coord_name] = coord
            elif coord_name == LocationKey:
                new_coords[coord_name] = xr.DataArray(
                    np.arange(n_clusters, dtype=coord.dtype),
                    dims=[LocationKey],
                    attrs=coord.attrs,
                )
            else:
                new_coords[coord_name] = cls._aggregate_variable(
                    coord,
                    kept_indices=kept_indices,
                    group_starts=group_starts,
                    first_obs_indices=first_obs_indices,
                    aggregation=aggregation,
                    is_longitude=(coord_name == LongitudeKey),
                )

        return xr.Dataset(data_vars=new_data_vars, coords=new_coords, attrs=ds.attrs)

    @staticmethod
    def _reduceat_nanmean(
        moved_kept: np.ndarray,
        group_starts: np.ndarray,
        out_dtype: np.dtype,
    ) -> np.ndarray:
        """Vectorized NaN-aware mean along axis 0 using np.add.reduceat."""
        valid = np.isfinite(moved_kept)
        clean = np.where(valid, moved_kept, 0.0)
        sums = np.add.reduceat(clean, group_starts, axis=0)
        counts = np.add.reduceat(valid.astype(np.int64), group_starts, axis=0)
        with np.errstate(divide="ignore", invalid="ignore"):
            return (sums / counts).astype(out_dtype)

    @classmethod
    def _aggregate_variable(
        cls,
        da: xr.DataArray,
        kept_indices: np.ndarray,
        group_starts: np.ndarray,
        first_obs_indices: np.ndarray,
        aggregation: str,
        is_longitude: bool = False,
    ) -> xr.DataArray:
        loc_axis = da.get_axis_num(LocationKey)
        vals = da.values

        # 1. Continuous physical variables (Radiance, BrightnessTemp, Lat, Lon)
        if np.issubdtype(vals.dtype, np.floating):
            moved = np.moveaxis(vals, loc_axis, 0)[kept_indices]

            if aggregation == "mean":
                if is_longitude:
                    # Circular mean to handle antimeridian / 0-360 wrap-around
                    rad = np.radians(moved)
                    mean_sin = cls._reduceat_nanmean(np.sin(rad), group_starts, np.float64)
                    mean_cos = cls._reduceat_nanmean(np.cos(rad), group_starts, np.float64)
                    mean_deg = np.degrees(np.arctan2(mean_sin, mean_cos))
                    # Preserve [0, 360) vs [-180, 180] convention of input array
                    if np.nanmin(moved) >= 0.0 and np.nanmax(moved) > 180.0:
                        mean_deg = mean_deg % 360.0
                    out = mean_deg.astype(vals.dtype)
                else:
                    out = cls._reduceat_nanmean(moved, group_starts, vals.dtype)
                out_arr = np.moveaxis(out, 0, loc_axis)

            else:  # aggregation == "median"
                n_clusters = len(group_starts)
                out_shape = list(moved.shape)
                out_shape[0] = n_clusters
                out = np.empty(out_shape, dtype=vals.dtype)
                ends = np.append(group_starts[1:], len(kept_indices))
                with np.errstate(all="ignore"):
                    for i, (s, e) in enumerate(zip(group_starts, ends)):
                        out[i] = moved[s] if (e - s == 1) else np.nanmedian(moved[s:e], axis=0)
                out_arr = np.moveaxis(out, 0, loc_axis)

        # 2. Observation Timestamps (offset-shifted reduceat prevents int64 overflow)
        elif np.issubdtype(vals.dtype, np.datetime64):
            moved_int = np.moveaxis(vals, loc_axis, 0)[kept_indices].view(np.int64)
            base_time = moved_int[0]
            offsets = moved_int - base_time
            sums = np.add.reduceat(offsets, group_starts, axis=0)
            counts = np.diff(np.append(group_starts, len(kept_indices)))
            # Broadcast cluster counts along trailing dimensions if multi-dimensional
            if sums.ndim > 1:
                counts = counts.reshape((-1,) + (1,) * (sums.ndim - 1))
            mean_int = base_time + (sums // counts)
            out_arr = np.moveaxis(mean_int.view(vals.dtype), 0, loc_axis)

        # 3. Discrete variables (QC Flags, station IDs, indices, strings)
        else:
            out_arr = np.take(vals, first_obs_indices, axis=loc_axis)

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
