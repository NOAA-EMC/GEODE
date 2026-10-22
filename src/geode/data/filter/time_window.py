from typing import Any

import xarray as xr
import numpy as np
from datetime import datetime, timezone

from geode.data.filter.factory import register_filter
from geode.data.filter.base import AndFilter

LocationKey = "Location"
TimeKey = "MetaData/dateTime"
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
        t0 = _to_utc_datetime64(self.arg[StartTimeKey])
        t1 = _to_utc_datetime64(self.arg[EndTimeKey])
        mask = ((dt[TimeKey] >= t0) & (dt[TimeKey] <= t1)).values
        return dt.map_over_datasets(lambda ds: ds.isel({LocationKey: mask}))

    @classmethod
    def _validate(cls, arg: dict[str, Any]) -> None:
        pass  # Not a user filter
