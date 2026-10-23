from typing import Any

import xarray as xr
import numpy as np
from datetime import datetime, timezone

from geode.data.filter.factory import register_filter
from geode.data.filter.base import AndFilter

LocationKey = "Location"
TimeKey = "MetaData/dateTime"
PeriodKey = "period_h"
WindowKey = "window_h"


@register_filter("periodic")
class PeriodicFilter(AndFilter):
    def __init__(self, arg: dict[str, Any]):
        super().__init__(arg)

    def apply(self, dt: xr.DataTree) -> xr.DataTree:
        start_time = dt[TimeKey].values[0]
        end_time = dt[TimeKey].values[-1]

        mask = np.zeros_like(dt[TimeKey].values, dtype=bool)
        current_time = start_time
        while current_time <= end_time:
            window = np.timedelta64(int(self.arg[WindowKey] * 60), 'm')
            period = np.timedelta64(int(self.arg[PeriodKey] * 60), 'm')
            mask |= (dt[TimeKey].values >= current_time) & (dt[TimeKey].values <= (current_time + window))
            current_time += period

        return dt.map_over_datasets(lambda ds: ds.isel({LocationKey: mask}))

    @classmethod
    def _validate(cls, arg: dict[str, Any]) -> None:
        if not isinstance(arg, dict):
            cls._validation_error("Arguments must be a dictionary with keys 'period_h' and 'window_h'.")
        
        if isinstance(arg, dict):
            if PeriodKey not in arg:
                cls._validation_error(f"Missing '{PeriodKey}' argument.")
            if WindowKey not in arg:
                cls._validation_error(f"Missing '{WindowKey}' argument.")
