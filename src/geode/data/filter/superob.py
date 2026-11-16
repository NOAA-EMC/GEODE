"""Spatial superobbing (observation aggregation) filter for GEODE DataTrees."""

import numbers
from typing import Any

import numpy as np
import pandas as pd
import xarray as xr

from geode.data.filter.base import AndFilter
from geode.data.filter.distance_utils import (
    cluster_by_distance_flat,
    validate_spatial_resolution,
)
from geode.data.filter.factory import register_filter
from geode.data.keys import LatitudeKey, LocationKey, LongitudeKey

try:
    from geode.data.keys import DatetimeKey as DateTimeKey
except ImportError:
    DateTimeKey = "MetaData/dateTime"


@register_filter("superobbing")
class SuperobbingFilter(AndFilter):
    """Aggregates nearby observations along the Location dimension into superobs."""

    def __init__(self, arg: dict[str, Any]):
        super().__init__(arg)

    def apply(self, datatree: xr.DataTree) -> xr.DataTree:
        was_sorted = bool(datatree.attrs.get("is_sorted", False))

        lats = np.asarray(datatree[LatitudeKey].variable.values, dtype=np.float64)
        lons = np.asarray(datatree[LongitudeKey].variable.values, dtype=np.float64)

        valid_mask = np.isfinite(lats) & np.isfinite(lons)
        valid_indices = np.where(valid_mask)[0]
        if len(valid_indices) == 0:
            result = datatree.map_over_datasets(
                lambda ds: ds.isel({LocationKey: []}) if LocationKey in ds.dims else ds
            )
            result.attrs["is_sorted"] = was_sorted
            return result

        grid = self.arg.get("grid")
        distance = self.arg.get("distance")
        aggregation = self.arg.get("aggregation", "mean")
        min_obs = int(self.arg.get("min_obs", 1))

        if grid is not None:
            if isinstance(grid, numbers.Real):
                dlat = dlon = float(grid)
            else:
                dlat, dlon = float(grid[0]), float(grid[1])
            orig, group_starts, counts = self._cluster_indices_grid(
                lats,
                lons,
                valid_indices,
                dlat=dlat,
                dlon=dlon,
            )
        elif distance is not None:
            units = self.arg.get("units", "km")
            distance_km = (
                float(distance) * 111.195 if units == "deg" else float(distance)
            )
            orig, group_starts, counts = self._cluster_indices_distance(
                lats,
                lons,
                valid_indices,
                distance_km=distance_km,
            )
        else:
            return datatree

        keep_mask = counts >= min_obs
        kept_starts = group_starts[keep_mask]
        kept_counts = counts[keep_mask]

        first_obs_indices = orig[kept_starts]
        if len(kept_starts) == 0:
            kept_indices = np.empty(0, dtype=np.int64)
            group_ids = np.empty(0, dtype=np.int64)
            kept_group_starts = np.empty(0, dtype=np.int64)
        else:
            member_offsets = np.concatenate(
                [
                    np.arange(s, s + c, dtype=np.int64)
                    for s, c in zip(kept_starts, kept_counts)
                ]
            )
            kept_indices = orig[member_offsets]
            group_ids = np.repeat(
                np.arange(len(kept_starts), dtype=np.int64), kept_counts
            )
            kept_group_starts = np.zeros(len(kept_counts), dtype=np.int64)
            if len(kept_counts) > 1:
                kept_group_starts[1:] = np.cumsum(kept_counts[:-1])

        result = datatree.map_over_datasets(
            lambda ds: self._aggregate_dataset(
                ds,
                kept_indices=kept_indices,
                first_obs_indices=first_obs_indices,
                group_ids=group_ids,
                group_starts=kept_group_starts,
                counts=kept_counts,
                aggregation=aggregation,
            )
        )
        return self._restore_timestamp_order(result, was_sorted=was_sorted)

    @staticmethod
    def _cluster_indices_grid(
        lats: np.ndarray,
        lons: np.ndarray,
        valid_indices: np.ndarray,
        dlat: float,
        dlon: float,
    ) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
        sub_lats = lats[valid_indices]
        sub_lons = np.mod(lons[valid_indices], 360.0)
        sub_lons[sub_lons >= 360.0] = 0.0

        lat_bins = np.floor((sub_lats + 90.0) / dlat).astype(np.int64)
        lat_center = np.clip((lat_bins + 0.5) * dlat - 90.0, -90.0, 90.0)
        n_lon = np.maximum(
            1, np.round(360.0 * np.cos(np.radians(lat_center)) / dlon)
        ).astype(np.int64)
        lon_bins = np.minimum(
            np.floor(sub_lons / 360.0 * n_lon).astype(np.int64), n_lon - 1
        )

        max_lon_bins = int(np.ceil(360.0 / dlon)) + 1
        cell_keys = lat_bins * max_lon_bins + lon_bins

        order = np.argsort(cell_keys, kind="stable")
        sorted_cells = cell_keys[order]
        starts = np.r_[0, np.where(sorted_cells[1:] != sorted_cells[:-1])[0] + 1]
        counts = np.diff(np.append(starts, len(order)))

        # Order clusters by their earliest input index
        sorted_orig = valid_indices[order]
        cluster_order = np.argsort(sorted_orig[starts], kind="stable")
        ordered_starts = starts[cluster_order]
        ordered_counts = counts[cluster_order]

        orig = np.concatenate(
            [sorted_orig[s : s + c] for s, c in zip(ordered_starts, ordered_counts)]
        )
        group_starts = np.zeros(len(ordered_counts), dtype=np.int64)
        if len(ordered_counts) > 1:
            group_starts[1:] = np.cumsum(ordered_counts[:-1])

        return orig, group_starts, ordered_counts

    @staticmethod
    def _cluster_indices_distance(
        lats: np.ndarray,
        lons: np.ndarray,
        valid_indices: np.ndarray,
        distance_km: float,
    ) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
        sub_lats = lats[valid_indices]
        sub_lons = lons[valid_indices]
        flat_indices, group_starts = cluster_by_distance_flat(
            sub_lats, sub_lons, distance_km=distance_km
        )
        if len(group_starts) == 0:
            empty = np.empty(0, dtype=np.int64)
            return empty, empty, empty

        orig = valid_indices[flat_indices]
        counts = np.diff(np.append(group_starts, len(orig)))
        return orig, group_starts, counts

    @classmethod
    def _aggregate_dataset(
        cls,
        ds: xr.Dataset,
        kept_indices: np.ndarray,
        first_obs_indices: np.ndarray,
        group_ids: np.ndarray,
        group_starts: np.ndarray,
        counts: np.ndarray,
        aggregation: str,
    ) -> xr.Dataset:
        if LocationKey not in ds.dims:
            return ds
        if len(first_obs_indices) == 0:
            return ds.isel({LocationKey: []})

        lon_var = LongitudeKey.split("/")[-1]
        dt_var = DateTimeKey.split("/")[-1]

        data_vars: dict[str, xr.DataArray] = {}
        for name, da in ds.data_vars.items():
            if LocationKey not in da.dims:
                data_vars[name] = da
                continue

            is_longitude = name in (LongitudeKey, lon_var)
            is_datetime = np.issubdtype(da.dtype, np.datetime64) or name in (
                DateTimeKey,
                dt_var,
            )
            data_vars[name] = cls._reduce_variable(
                da,
                kept_indices=kept_indices,
                first_obs_indices=first_obs_indices,
                group_ids=group_ids,
                group_starts=group_starts,
                counts=counts,
                method=aggregation,
                is_longitude=is_longitude,
                is_datetime=is_datetime,
            )

        coords: dict[str, Any] = {}
        for name, coord in ds.coords.items():
            if LocationKey in coord.dims:
                coords[name] = coord.isel({LocationKey: first_obs_indices})
            else:
                coords[name] = coord

        return xr.Dataset(data_vars=data_vars, coords=coords, attrs=ds.attrs)

    @staticmethod
    def _unwrap_longitudes_per_cluster(
        lons: np.ndarray,
        group_starts: np.ndarray,
        counts: np.ndarray,
    ) -> tuple[np.ndarray, bool]:
        """Unwrap 1D longitudes around each cluster's circular reference."""
        use_0_360 = not bool(np.any(lons < 0.0))
        rad = np.deg2rad(lons)
        valid = np.isfinite(rad)
        sin_sum = np.add.reduceat(np.where(valid, np.sin(rad), 0.0), group_starts)
        cos_sum = np.add.reduceat(np.where(valid, np.cos(rad), 0.0), group_starts)
        circ_ref = np.rad2deg(np.arctan2(sin_sum, cos_sum))
        ref_per_obs = np.repeat(circ_ref, counts)
        unwrapped = ref_per_obs + ((lons - ref_per_obs + 180.0) % 360.0) - 180.0
        return unwrapped, use_0_360

    @staticmethod
    def _restore_longitude_convention(lon: np.ndarray, use_0_360: bool) -> np.ndarray:
        """Wrap reduced longitudes back into the input [0, 360) or [-180, 180) range."""
        if use_0_360:
            out = np.mod(lon, 360.0)
            out[out >= 360.0] = 0.0
            return out
        return ((lon + 180.0) % 360.0) - 180.0

    @classmethod
    def _reduce_variable(
        cls,
        da: xr.DataArray,
        kept_indices: np.ndarray,
        first_obs_indices: np.ndarray,
        group_ids: np.ndarray,
        group_starts: np.ndarray,
        counts: np.ndarray,
        method: str,
        is_longitude: bool = False,
        is_datetime: bool = False,
    ) -> xr.DataArray:
        """Reduce a single variable along LocationKey without eager full-array reads."""
        if len(first_obs_indices) == 0:
            out = da.isel({LocationKey: []})
            out.encoding = dict(da.encoding)
            return out

        is_discrete = not (
            is_longitude or is_datetime or np.issubdtype(da.dtype, np.floating)
        )
        if method == "first" or is_discrete:
            out = da.isel({LocationKey: first_obs_indices})
            out.encoding = dict(da.encoding)
            return out

        # Slice only kept cluster members BEFORE reading .values from storage
        da_kept = da.isel({LocationKey: kept_indices})
        loc_axis = da_kept.get_axis_num(LocationKey)
        vals = np.asarray(da_kept.values)
        moved = np.moveaxis(vals, loc_axis, 0)
        trailing_shape = moved.shape[1:]
        n_groups = len(group_starts)

        if is_longitude:
            flat_lons = moved.reshape(-1)
            unwrapped, use_0_360 = cls._unwrap_longitudes_per_cluster(
                flat_lons, group_starts, counts
            )
            if method == "mean":
                valid = np.isfinite(unwrapped)
                sums = np.add.reduceat(np.where(valid, unwrapped, 0.0), group_starts)
                valid_counts = np.add.reduceat(valid.astype(np.int64), group_starts)
                raw_lon = np.where(
                    valid_counts > 0, sums / np.maximum(valid_counts, 1), np.nan
                )
            elif method == "median":
                raw_lon = (
                    pd.Series(unwrapped)
                    .groupby(group_ids, sort=False)
                    .median()
                    .to_numpy()
                )
            else:
                raise ValueError(f"Unsupported superob aggregation: {method}")
            reduced_moved = (
                cls._restore_longitude_convention(raw_lon, use_0_360)
                .reshape((n_groups, *trailing_shape))
                .astype(da.dtype, copy=False)
            )
        elif np.issubdtype(da.dtype, np.datetime64):
            unit = np.datetime_data(da.dtype)[0]
            epoch = np.datetime64("2020-01-01T00:00:00", unit)
            flat_dt = moved.reshape(-1)
            is_nat = np.isnat(flat_dt)
            offsets = np.where(is_nat, np.nan, (flat_dt - epoch).astype(np.int64))
            if method == "mean":
                valid = ~is_nat
                sums = np.add.reduceat(np.where(valid, offsets, 0.0), group_starts)
                valid_counts = np.add.reduceat(valid.astype(np.int64), group_starts)
                red_offsets = np.where(
                    valid_counts > 0, sums / np.maximum(valid_counts, 1), np.nan
                )
            elif method == "median":
                red_offsets = (
                    pd.Series(offsets)
                    .groupby(group_ids, sort=False)
                    .median()
                    .to_numpy()
                )
            else:
                raise ValueError(f"Unsupported superob aggregation: {method}")
            is_nan_out = np.isnan(red_offsets)
            safe_int = np.where(is_nan_out, 0, np.round(red_offsets)).astype(np.int64)
            td = safe_int.astype(f"timedelta64[{unit}]")
            reduced_moved = np.where(
                is_nan_out, np.datetime64("NaT", unit), epoch + td
            ).reshape((n_groups, *trailing_shape))
        else:
            flat = moved.reshape(len(moved), -1)
            if method == "mean":
                valid = np.isfinite(flat)
                sums = np.add.reduceat(np.where(valid, flat, 0.0), group_starts, axis=0)
                valid_counts = np.add.reduceat(
                    valid.astype(np.int64), group_starts, axis=0
                )
                reduced_flat = np.where(
                    valid_counts > 0, sums / np.maximum(valid_counts, 1), np.nan
                )
            elif method == "median":
                reduced_flat = (
                    pd.DataFrame(flat)
                    .groupby(group_ids, sort=False)
                    .median()
                    .to_numpy()
                )
            else:
                raise ValueError(f"Unsupported superob aggregation: {method}")

            if is_datetime and np.issubdtype(da.dtype, np.integer):
                reduced_flat = np.round(reduced_flat)
            reduced_moved = reduced_flat.reshape((n_groups, *trailing_shape)).astype(
                da.dtype, copy=False
            )

        out_vals = np.moveaxis(reduced_moved, 0, loc_axis)
        non_loc_coords = {
            k: v for k, v in da.coords.items() if LocationKey not in v.dims
        }
        out = xr.DataArray(
            out_vals,
            dims=da.dims,
            coords=non_loc_coords,
            attrs=da.attrs,
        )
        out.encoding = dict(da.encoding)
        return out

    @staticmethod
    def _restore_timestamp_order(
        result: xr.DataTree,
        was_sorted: bool,
    ) -> xr.DataTree:
        """Preserve monotonic MetaData/dateTime order when input was sorted."""
        if not was_sorted:
            if "is_sorted" in result.attrs:
                result.attrs["is_sorted"] = False
            return result

        try:
            dt_vals = np.asarray(result[DateTimeKey].variable.values)
        except KeyError:
            result.attrs["is_sorted"] = False
            return result

        if dt_vals.size == 0:
            result.attrs["is_sorted"] = True
            return result

        has_missing = (
            np.isnat(dt_vals).any()
            if np.issubdtype(dt_vals.dtype, np.datetime64)
            else not np.isfinite(dt_vals).all()
        )
        if has_missing:
            result.attrs["is_sorted"] = False
            return result

        sort_order = np.argsort(dt_vals, kind="stable")
        if not np.array_equal(sort_order, np.arange(len(sort_order))):
            result = result.map_over_datasets(
                lambda ds: (
                    ds.isel({LocationKey: sort_order}) if LocationKey in ds.dims else ds
                )
            )
        result.attrs["is_sorted"] = True
        return result

    @classmethod
    def _validate(cls, arg: dict[str, Any]) -> None:
        validate_spatial_resolution(arg, cls._validation_error)
        if "units" in arg and arg["units"] not in ("km", "deg"):
            cls._validation_error(f"Invalid units: {arg['units']!r}")
        if "aggregation" in arg and arg["aggregation"] not in (
            "mean",
            "median",
            "first",
        ):
            cls._validation_error(f"Invalid aggregation: {arg['aggregation']!r}")
        if "min_obs" in arg:
            min_obs = arg["min_obs"]
            if (
                isinstance(min_obs, (bool, np.bool_))
                or not isinstance(min_obs, numbers.Integral)
                or int(min_obs) < 1
            ):
                cls._validation_error(
                    f"Invalid 'min_obs': {min_obs!r}. Expected an integer >= 1."
                )
