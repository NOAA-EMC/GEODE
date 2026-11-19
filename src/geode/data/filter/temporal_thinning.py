"""Temporal thinning filter for GEODE observation DataTrees."""

import datetime
from bisect import bisect_left, insort
from typing import Any

import numpy as np
import pandas as pd
import xarray as xr

from geode.data.filter.base import AndFilter
from geode.data.filter.factory import register_filter
from geode.data.keys import IsSortedFlag, LocationKey, TimeKey


def _to_nanoseconds(
    value: int | float | str | datetime.timedelta | np.timedelta64 | pd.Timedelta,
    units: str = "s",
) -> int:
    """Convert a duration specification into strictly positive integer nanoseconds."""
    if isinstance(value, (bool, np.bool_)):
        raise ValueError(f"Invalid time duration: {value!r}")

    if isinstance(value, (datetime.timedelta, np.timedelta64, pd.Timedelta)):
        td = pd.to_timedelta(value)
    elif isinstance(value, (int, float, np.number)):
        if not np.isfinite(float(value)):
            raise ValueError(f"Time duration must be finite, got: {value!r}")
        td = pd.to_timedelta(float(value), unit=units)
    else:
        td = pd.to_timedelta(value)

    if pd.isna(td):
        raise ValueError(f"Invalid time duration: {value!r}")

    ns = int(td.value)
    if ns <= 0:
        raise ValueError(f"Time duration must be positive, got: {value!r}")
    return ns


def _ref_to_nanoseconds(reference_time: str | pd.Timestamp | np.datetime64) -> int:
    """Convert an anchor timestamp into epoch nanoseconds."""
    if isinstance(reference_time, (bool, np.bool_, int, float, np.number)):
        raise ValueError(f"Invalid reference_time: {reference_time!r}")
    ts = pd.Timestamp(reference_time)
    if pd.isna(ts):
        raise ValueError(f"Invalid reference_time: {reference_time!r}")
    if ts.tzinfo is not None:
        ts = ts.tz_convert("UTC")
    return int(ts.value)


@register_filter("temporal_thinning")
class TemporalThinningFilter(AndFilter):
    """Subsamples observations along the Location dimension by time interval or spacing."""

    def __init__(self, arg: dict[str, Any]):
        super().__init__(arg)

    def apply(self, datatree: xr.DataTree) -> xr.DataTree:
        was_sorted = bool(datatree.attrs.get(IsSortedFlag, False))
        time_key = self.arg.get("time_key", TimeKey)
        times = np.asarray(datatree[time_key].variable.values, dtype="datetime64[ns]")

        valid_mask = ~np.isnat(times)
        valid_indices = np.where(valid_mask)[0]
        if len(valid_indices) == 0:
            result = datatree.map_over_datasets(
                lambda ds: ds.isel({LocationKey: []}) if LocationKey in ds.dims else ds
            )
            result.attrs[IsSortedFlag] = was_sorted
            return result

        sub_times_ns = times[valid_indices].view(np.int64)
        units = self.arg.get("units", "s")
        strategy = self.arg.get("strategy", "center")
        align = self.arg.get("align", "center")
        seed = self.arg.get("seed", 42)
        ref_ns = _ref_to_nanoseconds(
            self.arg.get("reference_time", "1970-01-01T00:00:00")
        )

        # 1. Fixed-interval bin thinning (e.g., one observation per hour centered on :00)
        if self.arg.get("interval") is not None:
            interval_ns = _to_nanoseconds(self.arg["interval"], units=units)
            selected = self._thin_indices_interval(
                sub_times_ns=sub_times_ns,
                valid_indices=valid_indices,
                interval_ns=interval_ns,
                ref_ns=ref_ns,
                align=align,
                strategy=strategy,
                seed=seed,
            )
        # 2. Minimum-separation thinning (guarantees |t_i - t_j| >= min_spacing)
        elif self.arg.get("min_spacing") is not None:
            spacing_ns = _to_nanoseconds(self.arg["min_spacing"], units=units)
            selected = self._thin_indices_spacing(
                sub_times_ns=sub_times_ns,
                valid_indices=valid_indices,
                spacing_ns=spacing_ns,
                ref_ns=ref_ns,
                strategy=strategy,
                seed=seed,
            )
        else:
            return datatree

        result = datatree.map_over_datasets(
            lambda ds: (
                ds.isel({LocationKey: selected}) if LocationKey in ds.dims else ds
            )
        )
        result.attrs[IsSortedFlag] = was_sorted
        return result

    @staticmethod
    def _thin_indices_interval(
        sub_times_ns: np.ndarray,
        valid_indices: np.ndarray,
        interval_ns: int,
        ref_ns: int,
        align: str,
        strategy: str,
        seed: int,
    ) -> np.ndarray:
        # align="center" places bin boundaries at ref + (k - 0.5)*dt so centers sit at ref + k*dt
        offset_ns = ref_ns - (interval_ns // 2) if align == "center" else ref_ns
        bin_ids = (sub_times_ns - offset_ns) // interval_ns

        if strategy == "center":
            bin_centers_ns = (
                ref_ns + bin_ids * interval_ns
                if align == "center"
                else ref_ns + bin_ids * interval_ns + (interval_ns // 2)
            )
            dist = np.abs(sub_times_ns - bin_centers_ns)
            order = np.lexsort((dist, bin_ids))
        elif strategy == "first":
            order = np.lexsort((sub_times_ns, bin_ids))
        elif strategy == "last":
            order = np.lexsort((-sub_times_ns, bin_ids))
        elif strategy == "random":
            rand_keys = np.random.default_rng(seed).random(len(bin_ids))
            order = np.lexsort((rand_keys, bin_ids))
        else:
            raise ValueError(f"Invalid temporal thinning strategy: {strategy}")

        sorted_bins = bin_ids[order]
        first_in_bin = np.r_[True, sorted_bins[1:] != sorted_bins[:-1]]
        return np.sort(valid_indices[order[first_in_bin]])

    @staticmethod
    def _thin_indices_spacing(
        sub_times_ns: np.ndarray,
        valid_indices: np.ndarray,
        spacing_ns: int,
        ref_ns: int,
        strategy: str,
        seed: int,
    ) -> np.ndarray:
        idx_tiebreaker = np.arange(len(sub_times_ns))

        if strategy == "first":
            order = np.lexsort((idx_tiebreaker, sub_times_ns))
        elif strategy == "last":
            order = np.lexsort((idx_tiebreaker, -sub_times_ns))
        elif strategy == "random":
            order = np.random.default_rng(seed).permutation(len(sub_times_ns))
        elif strategy == "center":
            nearest_k = (sub_times_ns - ref_ns + (spacing_ns // 2)) // spacing_ns
            nearest_anchor = ref_ns + nearest_k * spacing_ns
            dist = np.abs(sub_times_ns - nearest_anchor)
            order = np.lexsort((sub_times_ns, dist))
        else:
            raise ValueError(f"Invalid temporal thinning strategy: {strategy}")

        accepted_times: list[int] = []
        selected: list[int] = []

        for idx in order:
            t = int(sub_times_ns[idx])
            pos = bisect_left(accepted_times, t)
            if pos > 0 and (t - accepted_times[pos - 1]) < spacing_ns:
                continue
            if pos < len(accepted_times) and (accepted_times[pos] - t) < spacing_ns:
                continue
            insort(accepted_times, t)
            selected.append(int(valid_indices[idx]))

        return np.sort(np.asarray(selected, dtype=np.int64))

    @classmethod
    def _validate(cls, arg: dict[str, Any]) -> None:
        has_interval = arg.get("interval") is not None
        has_spacing = arg.get("min_spacing") is not None

        if not has_interval and not has_spacing:
            cls._validation_error(
                "Temporal thinning requires either 'interval' or 'min_spacing'."
            )
        if has_interval and has_spacing:
            cls._validation_error(
                "Specify either 'interval' or 'min_spacing', not both."
            )

        units = arg.get("units", "s")
        try:
            if has_interval:
                _to_nanoseconds(arg["interval"], units=units)
            if has_spacing:
                _to_nanoseconds(arg["min_spacing"], units=units)
            if "reference_time" in arg:
                _ref_to_nanoseconds(arg["reference_time"])
        except ValueError as exc:
            cls._validation_error(str(exc))

        if "strategy" in arg and arg["strategy"] not in (
            "center",
            "first",
            "last",
            "random",
        ):
            cls._validation_error(f"Invalid strategy: {arg['strategy']}")
        if "align" in arg and arg["align"] not in ("center", "start"):
            cls._validation_error(f"Invalid align mode: {arg['align']}")
