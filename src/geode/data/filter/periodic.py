from typing import Any

import xarray as xr
import numpy as np
from datetime import datetime, timezone

from geode.data.filter.factory import register_filter
from geode.data.filter.base import AndFilter
from geode.data.keys import LocationKey, TimeKey

PeriodKey = "period"
WindowKey = "window"


@register_filter("periodic")
class PeriodicFilter(AndFilter):
    def __init__(self, arg: dict[str, Any]):
        super().__init__(arg)

    def apply(self, dt: xr.DataTree) -> xr.DataTree:
        start_time = dt[TimeKey].values[0]
        end_time = dt[TimeKey].values[-1]

        mask = np.zeros_like(dt[TimeKey].values, dtype=bool)
        current_time = start_time

        if isinstance(self.arg[PeriodKey], str):
            self.arg[PeriodKey] = self._parse_timedelta_str(PeriodKey)
        if isinstance(self.arg[WindowKey], str):
            self.arg[WindowKey] = self._parse_timedelta_str(WindowKey)

        if isinstance(self.arg[PeriodKey], (int, float)):
            self.arg[PeriodKey] = np.timedelta64(int(self.arg[PeriodKey] * 60), "m")
        if isinstance(self.arg[WindowKey], (int, float)):
            self.arg[WindowKey] = np.timedelta64(int(self.arg[WindowKey] * 60), "m")

        window = self.arg[WindowKey]
        period = self.arg[PeriodKey]

        while current_time <= end_time:
            mask |= (dt[TimeKey].values >= current_time) & (
                dt[TimeKey].values <= (current_time + window)
            )
            current_time += period

        return dt.map_over_datasets(lambda ds: ds.isel({LocationKey: mask}))

    def _parse_timedelta_str(self, key: str) -> np.timedelta64:
        time_str = self.arg[key]
        parts = list(map(int, time_str.split(":")))
        if len(parts) == 3:
            hours, minutes, seconds = parts
        elif len(parts) == 2:
            hours, minutes = parts
            seconds = 0
        elif len(parts) == 1:
            hours = parts[0]
            minutes = 0
            seconds = 0
        else:
            raise ValueError(f"Invalid time format for {key}: {time_str}")
        return np.timedelta64(hours * 3600 + minutes * 60 + seconds, "s")

    @classmethod
    def _validate(cls, arg: dict[str, Any]) -> None:
        if not isinstance(arg, dict):
            cls._validation_error(
                "Arguments must be a dictionary with keys 'period' and 'window'."
            )

        if PeriodKey not in arg:
            cls._validation_error(f"Missing '{PeriodKey}' argument.")

        if WindowKey not in arg:
            cls._validation_error(f"Missing '{WindowKey}' argument.")

        if not isinstance(arg[PeriodKey], (str, int, float, np.timedelta64)):
            cls._validation_error(
                f"'{PeriodKey}' must be an int, float, or np.timedelta64."
            )

        if not isinstance(arg[WindowKey], (str, int, float, np.timedelta64)):
            cls._validation_error(
                f"'{WindowKey}' must be an int, float, or np.timedelta64."
            )
