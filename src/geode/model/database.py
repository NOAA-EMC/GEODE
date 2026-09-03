
import os
import sys

if __name__ == "__main__":
    sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))
    print (sys.path)

import argparse
from datetime import datetime

import xarray as xr
from sqlalchemy import create_engine

from geode.configs.geode_config import geode_config
from geode.model.catalog import Catalog
from geode.model.data_file import File
from geode.model.data_set import DataSet


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
    data_file = catalog.session.query(File).filter(
        File.data_set_id == data_set.id,
        File.start_time <= time,
        File.end_time >= time
    ).first()
    if data_file is None:
        raise ValueError(f"No data file found for data set '{data_set_name}' at time '{time}'.")
    return data_file.file_path


def add_data(data: xr.DataTree, catalog: Catalog, data_set_name: str) -> None:
    data_set = get_data_set(catalog, data_set_name)

    # Split the data into individual file chunks based on the time dimension. Each chunk will be saved as a separate file.
    for time in data.time.values:
        # Get the data for this time
        data_at_time = data.sel(time=time)

        # Determine the file path for this data. The file path will be based on the data set name and the time.
        file_path = f"{data_set_name}/{time.strftime('%Y%m%d%H%M%S')}.nc"

        # Save the data to a NetCDF file
        data_at_time.to_netcdf(file_path)

        # Add an entry to the database for this file
        new_data_file = File(
            data_set_id=data_set.id,
            file_path=file_path,
            start_time=time,
            end_time=time  # Assuming each file contains only one time point
        )
        catalog.session.add(new_data_file)
        catalog.session.commit()

def create_db() -> None:
    # Create a new SQLite database and return the engine
    db_config = geode_config.database
    if db_config.type == "sqlite":
        engine = create_engine(f"sqlite:///{db_config.full_db_path}")
    else:
        raise ValueError(f"Unsupported database type: {db_config.type}")

    Catalog.metadata.create_all(engine)
    return engine

if __name__ == "__main__":
    argument_parser = argparse.ArgumentParser(description="Create the GEODE database and tables.")
    argument_parser.add_argument(
        "--config",
        type=str,
        required=False,
        default=os.path.join(os.path.dirname(__file__), "../configs/geode_config.yaml"),
        help="Path to the GEODE configuration YAML file."
    )
    argument_parser.add_argument(
        "--create-db",
        type=str,
        required=False,
        help="Create a new database from configuration."
    )
    args = argument_parser.parse_args()

    if args.create_db:
        create_db()
    
