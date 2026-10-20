from typing import Any

import xarray as xr
import numpy as np
from datetime import datetime, timezone

from geode.data.filter.apply import register_filter
from geode.data.filter.base import FilterBase

TimeKey = "MetaData/dateTime"
StartTimeKey = "start_time"
EndTimeKey = "end_time"


def _to_utc_datetime64(value: datetime) -> np.datetime64:
    # Stored dateTime values are naive UTC; naive inputs are assumed to already be UTC.
    if value.tzinfo is not None:
        value = value.astimezone(timezone.utc).replace(tzinfo=None)
    return np.datetime64(value, "s")


@register_filter("time_window")
class TimeWindowFilter(FilterBase):

    @classmethod
    def _make_mask(cls, ds: xr.DataTree, kwargs: dict[str, Any]):
        t0 = _to_utc_datetime64(kwargs[StartTimeKey])
        t1 = _to_utc_datetime64(kwargs[EndTimeKey])
        return ((ds[TimeKey] >= t0) & (ds[TimeKey] <= t1)).values

    @classmethod
    def _validate(cls, kwargs: dict[str, Any]) -> None:
        if not isinstance(kwargs, dict):
            cls._validation_error("Arguments must be a dictionary with keys 'start_time' and 'end_time'.")
        if StartTimeKey not in kwargs or EndTimeKey not in kwargs:
            cls._validation_error("Arguments must contain 'start_time' and 'end_time'.")
        start_time, end_time = kwargs[StartTimeKey], kwargs[EndTimeKey]
        if not isinstance(start_time, datetime) or not isinstance(end_time, datetime):
            cls._validation_error("Arguments must be datetime instances.")
        if start_time >= end_time:
            cls._validation_error("start_time must be earlier than end_time.")
