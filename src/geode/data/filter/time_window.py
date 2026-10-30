from typing import Any

import numpy as np
import xarray as xr

from geode.data.filter.base import AndFilter
from geode.data.filter.factory import register_filter
from geode.data.keys import IsSortedFlag, LocationKey, TimeKey

StartTimeKey = "start_time"
EndTimeKey = "end_time"


@register_filter("time_window")
class TimeWindowFilter(AndFilter):
    def __init__(self, arg: dict[str, Any]):
        super().__init__(arg)

    def apply(self, dt: xr.DataTree) -> xr.DataTree:
        is_sorted = dt.attrs.get(IsSortedFlag, False)

        border = np.timedelta64(0, "s")
        if not is_sorted:
            # look 30 minutes beyond the time window for unsorted data
            border = np.timedelta64(30, "m")

        # Decimate the the data tree based on the time window first. This
        # eliminates the vast majority of irrelevant data points without
        # loading all the datetime values into memory.
        dt = self._slice_window(dt, border)

        if not is_sorted:
            # Filter out any remaining data points outside the time window.
            dt = self._apply_mask(dt)

        return dt

    def _slice_window(self, dt: xr.DataTree, border: np.timedelta64) -> xr.DataTree:

        def _find_bound(times: xr.DataArray, target: np.datetime64) -> int:
            start = 0
            end = times.sizes[LocationKey]

            while start < end:
                current_pos = (start + end) // 2
                timestamp = times.isel({LocationKey: current_pos}).values[()]

                if timestamp < target:
                    start = current_pos + 1
                else:
                    end = current_pos

            return start

        start = _find_bound(dt[TimeKey], self.arg[StartTimeKey] - border)
        end = _find_bound(dt[TimeKey], self.arg[EndTimeKey] + border)
        return dt.map_over_datasets(
            lambda ds: ds.isel({LocationKey: slice(start, end)})
        )

    def _apply_mask(self, dt: xr.DataTree) -> xr.DataTree:
        mask = (
            (dt[TimeKey] >= self.arg[StartTimeKey])
            & (dt[TimeKey] < self.arg[EndTimeKey])
        ).values

        if not np.all(mask):
            return dt.map_over_datasets(lambda ds: ds.isel({LocationKey: mask}))

        return dt

    @classmethod
    def _validate(cls, arg: dict[str, Any]) -> None:
        if StartTimeKey not in arg:
            raise ValueError(f"Missing required key: {StartTimeKey}")
        if EndTimeKey not in arg:
            raise ValueError(f"Missing required key: {EndTimeKey}")

        if not isinstance(arg[StartTimeKey], np.datetime64):
            raise TypeError(f"{StartTimeKey} must be a np.datetime64")
        if not isinstance(arg[EndTimeKey], np.datetime64):
            raise TypeError(f"{EndTimeKey} must be a np.datetime64")
