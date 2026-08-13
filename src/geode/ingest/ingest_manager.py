from datetime import datetime
import xarray as xr



def put_obs(data_type: str, data: xr.DataTree) -> None:
    # check DB for data_type and create if not exists
    # check the DB to see if it has a 

def get_obs(data_type: str, 
            start_time: datetime, 
            end_time: datetime,
            filter: dict = None) -> xr.DataTree:
    pass