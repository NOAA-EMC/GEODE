
from datetime import datetime
import xarray as xr

from .catalog import Catalog
from .data_set import DataSet
from .data_file import DataFile


def has_data_set(catalog: Catalog, data_set_name: str) -> bool:
    return catalog.session.query(DataSet).filter_by(name=data_set_name).first() is not None

def add_data_set(catalog: Catalog, data_set_name: str) -> DataSet:
    if has_data_set(catalog, data_set_name):
        raise ValueError(f"Data set '{data_set_name}' already exists in the catalog.")
    
    new_data_set = DataSet(name=data_set_name)
    catalog.session.add(new_data_set)
    catalog.session.commit()
    return new_data_set

def get_data_set(catalog: Catalog, data_set_name: str) -> DataSet:
    data_set = catalog.session.query(DataSet).filter_by(name=data_set_name).first()
    if data_set is None:
        raise ValueError(f"Data set '{data_set_name}' does not exist in the catalog.")
    return data_set

def get_data_file(catalog: Catalog, data_set_name: str, time: datetime) -> str:
    data_set = get_data_set(catalog, data_set_name)

    # Find the data file that includes the given time. The time given is the time of the observation,
    # so we need to find the data file that contains that observation. We can do this by checking the
    # start and end times of each data file in the data set.
    data_file = catalog.session.query(DataFile).filter(
        DataFile.data_set_id == data_set.id,
        DataFile.start_time <= time,
        DataFile.end_time >= time
    ).first()
    if data_file is None:
        raise ValueError(f"No data file found for data set '{data_set_name}' at time '{time}'.")
    return data_file.file_path

def add_data(data: xr.DataTree, catalog: Catalog, data_set_name: str) -> None:
    data_set = get_data_set(catalog, data_set_name)

    # Split the data into individual file chunks based on the time dimension. Each chunk will be saved as a separate file.
    