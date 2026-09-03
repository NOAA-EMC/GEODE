from datetime import datetime

import xarray as xr

from geode.data.data_manager import data_manager


def get(
    data_type: str,
    start_time: datetime | str,
    end_time: datetime | str,
    vars : list[str] | None = None,
    filter:dict | None = None,
) -> xr.DataTree:

    if isinstance(start_time, str):
        start_time = datetime.fromisoformat(start_time)
    if isinstance(end_time, str):
        end_time = datetime.fromisoformat(end_time)

    return data_manager.get(data_type, start_time, end_time, vars=vars, filter=filter)
