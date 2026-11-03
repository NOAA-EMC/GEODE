from datetime import datetime
from typing import Any

import numpy as np
import xarray as xr

from geode.data.manager import data_manager


def _decode_time(value: datetime | np.datetime64 | str) -> np.datetime64:
    if isinstance(value, np.datetime64):
        return value
    if isinstance(value, datetime):
        return np.datetime64(value, "us")
    if isinstance(value, str):
        return np.datetime64(datetime.fromisoformat(value), "us")
    raise ValueError(f"Invalid time format: {value}")


def get(
    data_type: str,
    start_time: datetime | np.datetime64 | str,
    end_time: datetime | np.datetime64 | str,
    filters: list[dict[str, Any]] | None = None,
) -> xr.DataTree:

    return data_manager.get(
        data_type,
        _decode_time(start_time),
        _decode_time(end_time),
        filters=filters,
    )
