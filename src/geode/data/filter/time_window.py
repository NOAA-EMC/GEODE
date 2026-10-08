from typing import Any

import xarray as xr
import numpy as np
from datetime import datetime, timezone as UTC

from geode.data.filter.apply import register_filter
from geode.data.filter.base import Filter, FilterType, ValidationError


TimeKey = "time"

@register_filter("time_window")
class TimeWindowFilter(FilterType):

    @classmethod
    def validate(cls, args: tuple[datetime, datetime]) -> None:
        if not isinstance(args, tuple) or len(args) != 2:
            cls._validation_error("Arguments must be a tuple of (start_time, end_time).")
        start_time, end_time = args
        if not isinstance(start_time, datetime) or not isinstance(end_time, datetime):
            cls._validation_error("Arguments must be datetime instances.")

    @classmethod
    def make(cls, args: tuple[datetime, datetime]) -> Filter:
        start_time, end_time = args
        return Filter(kind=Filter.Kind.Select, kwargs={TimeKey: slice(start_time, end_time)})
