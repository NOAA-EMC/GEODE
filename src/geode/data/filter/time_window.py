from datetime import UTC, datetime
from typing import Any

import numpy as np
import xarray as xr

from geode.data.filter.base import AndFilter
from geode.data.filter.factory import register_filter
from geode.data.keys import IsSortedFlag, LocationKey, TimeKey

StartTimeKey = "start_time"
EndTimeKey = "end_time"


def _to_utc_datetime64(value: datetime) -> np.datetime64:
    # Stored dateTime values are naive UTC; naive inputs are assumed to already be UTC.
    if value.tzinfo is not None:
        value = value.astimezone(UTC).replace(tzinfo=None)
    return np.datetime64(value, "s")


@register_filter("time_window")
class TimeWindowFilter(AndFilter):
    def __init__(self, arg: dict[str, Any]):
        super().__init__(arg)

        self.t0 = _to_utc_datetime64(arg[StartTimeKey])
        self.t1 = _to_utc_datetime64(arg[EndTimeKey])

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

        def _find_bound(
            times: xr.DataArray,
            target: np.datetime64
        ) -> int:

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

        start = _find_bound(dt[TimeKey], self.t0 - border)
        end = _find_bound(dt[TimeKey], self.t1 + border)
        return dt.map_over_datasets(
            lambda ds: ds.isel({LocationKey: slice(start, end)})
        )

    def _apply_mask(self, dt: xr.DataTree) -> xr.DataTree:
        mask = ((dt[TimeKey] >= self.t0) & (dt[TimeKey] < self.t1)).values

        if not np.all(mask):
            return dt.map_over_datasets(lambda ds: ds.isel({LocationKey: mask}))

        return dt

    @classmethod
    def _validate(cls, arg: dict[str, Any]) -> None:
        pass  # Not a user filter
