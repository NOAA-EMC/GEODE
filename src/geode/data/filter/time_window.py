from typing import Any

import xarray as xr
import numpy as np
from datetime import datetime, timezone

from geode.data.filter.factory import register_filter
from geode.data.filter.base import AndFilter
from geode.data.keys import LocationKey, TimeKey, IsSortedFlag

StartTimeKey = "start_time"
EndTimeKey = "end_time"


def _to_utc_datetime64(value: datetime) -> np.datetime64:
    # Stored dateTime values are naive UTC; naive inputs are assumed to already be UTC.
    if value.tzinfo is not None:
        value = value.astimezone(timezone.utc).replace(tzinfo=None)
    return np.datetime64(value, "s")


@register_filter("time_window")
class TimeWindowFilter(AndFilter):
    def __init__(self, arg: dict[str, Any]):
        super().__init__(arg)

        self.t0 = _to_utc_datetime64(arg[StartTimeKey])
        self.t1 = _to_utc_datetime64(arg[EndTimeKey])

    def apply(self, dt: xr.DataTree) -> xr.DataTree:
        # Decimate the the data tree based on the time window first. This
        # eliminates the vast majority of irrelevant data points without
        # loading all the datetime values into memory.
        dt = self._apply_to_sorted_data(dt)

        if not dt.attrs.get(IsSortedFlag, False):
            # Guard against unsorted data in the remaining subset.
            dt = self._apply_to_unsorted_data(dt)
        
        return dt

    def _apply_to_sorted_data(self, dt: xr.DataTree) -> xr.DataTree:

        def _find_bound(
            times: xr.DataArray,
            target: np.datetime64,
            from_right: bool,
        ) -> int:

            start = 0
            end = times.sizes[LocationKey]

            while start < end:
                current_pos = (end + start) // 2
                timestamp = times.isel({LocationKey: current_pos}).values[()]

                if timestamp < target or (from_right and timestamp == target):
                    start = current_pos + 1
                else:
                    end = current_pos

            return start

        start = _find_bound(dt[TimeKey], self.t0, from_right=False)
        end = _find_bound(dt[TimeKey], self.t1, from_right=True)
        return dt.map_over_datasets(
            lambda ds: ds.isel({LocationKey: slice(start, end)})
        )

    def _apply_to_unsorted_data(self, dt: xr.DataTree) -> xr.DataTree:
        mask = ((dt[TimeKey] >= self.t0) & (dt[TimeKey] <= self.t1)).values

        if not np.all(mask):
            return dt.map_over_datasets(lambda ds: ds.isel({LocationKey: slice(0, 0)}))

        return dt

    @classmethod
    def _validate(cls, arg: dict[str, Any]) -> None:
        pass  # Not a user filter
