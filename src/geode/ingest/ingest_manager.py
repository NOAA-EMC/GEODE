from datetime import datetime
import xarray as xr

def put_obs(data_type: str, data: xr.DataTree) -> None:
    pass

def get_obs(data_type: str, 
            start_time: datetime, 
            end_time: datetime,
            filter: dict = None) -> xr.DataTree:
    pass