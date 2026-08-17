from datetime import datetime
import xarray as xr

from geode.lake.lake_manager import lake_manager


def get(data_type: str, start_time: datetime, end_time: datetime) -> xr.DataTree:
    return lake_manager.get(data_type, start_time, end_time)
