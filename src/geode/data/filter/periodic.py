from typing import Any

import numpy as np
import xarray as xr

from geode.data.filter.base import AndFilter
from geode.data.filter.factory import register_filter
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

        period = self._decode_time(self.arg[PeriodKey])
        window = self._decode_time(self.arg[WindowKey])

        while current_time <= end_time:
            mask |= (dt[TimeKey].values >= current_time) & (
                dt[TimeKey].values <= (current_time + window)
            )
            current_time += period

        return dt.map_over_datasets(lambda ds: ds.isel({LocationKey: mask}))

    @classmethod
    def _decode_time(cls, time: np.datetime64 | int | float | str) -> np.timedelta64:

        def _parse_timedelta_str(time_str: str) -> np.timedelta64:
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
                cls._validation_error(f"Invalid time format: {time_str}")
            return np.timedelta64(hours * 3600 + minutes * 60 + seconds, "s")

        if isinstance(time, np.timedelta64):
            return time
        elif isinstance(time, int):
            return np.timedelta64(time, "h")
        elif isinstance(time, float):
            return np.timedelta64(int(time * 3600), "s")
        elif isinstance(time, str):
            return _parse_timedelta_str(time)

        cls._validation_error(f"Invalid time format for {time}")

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

        period = cls._decode_time(arg[PeriodKey])
        window = cls._decode_time(arg[WindowKey])

        if period <= np.timedelta64(0, "s"):
            cls._validation_error(f"'{PeriodKey}' must be positive.")

        if window <= np.timedelta64(0, "s"):
            cls._validation_error(f"'{WindowKey}' must be positive.")

        if period < window:
            cls._validation_error(
                f"'{PeriodKey}' must be greater than or equal to '{WindowKey}'."
            )
