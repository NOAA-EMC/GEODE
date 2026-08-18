from datetime import datetime

import xarray as xr

from geode.data.data_manager import data_manager


def get(data_type: str, start_time: datetime, end_time: datetime) -> xr.DataTree:
    return data_manager.get(data_type, start_time, end_time)
