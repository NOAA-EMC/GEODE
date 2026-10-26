from typing import Any

import xarray as xr
import numpy as np
from datetime import datetime, timezone

from geode.data.filter.factory import register_filter
from geode.data.filter.base import AndFilter
from geode.data.keys import LocationKey, TimeKey

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

    def apply(self, dt: xr.DataTree) -> xr.DataTree:
        return self._apply_to_sorted_data(dt)

    def _apply_to_sorted_data(self, dt: xr.DataTree) -> xr.DataTree:
        
        def _find_bound(times: xr.DataArray, target: np.datetime64, from_right: bool) -> int:
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

        t0 = _to_utc_datetime64(self.arg[StartTimeKey])
        t1 = _to_utc_datetime64(self.arg[EndTimeKey])

        start = _find_bound(dt[TimeKey], t0, from_right=False)
        end = _find_bound(dt[TimeKey], t1, from_right=True)
        return dt.map_over_datasets(lambda ds: ds.isel({LocationKey: slice(start, end)}))
    
    def _apply_to_unsorted_data(self, dt: xr.DataTree) -> xr.DataTree:
        t0 = _to_utc_datetime64(self.arg[StartTimeKey])
        t1 = _to_utc_datetime64(self.arg[EndTimeKey])

        mask = ((dt[TimeKey] >= t0) & (dt[TimeKey] <= t1)).values
        return dt.map_over_datasets(lambda ds: ds.isel({LocationKey: mask}))

    @classmethod
    def _validate(cls, arg: dict[str, Any]) -> None:
        pass  # Not a user filter
