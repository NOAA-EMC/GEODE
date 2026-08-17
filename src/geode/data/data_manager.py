import os
from datetime import datetime

import zarr
import icechunk as ic
import xarray as xr

from geode.configs.geode_config import geode_config


class DataManager:
    def __init__(self):
        self.config = geode_config.data_lake

    def get_file_path(self, data_type :str, timestamp: datetime = None) -> str:
        raise NotImplementedError("This method should be implemented by subclasses.")

    def put(self, data_type: str, data_tree: xr.DataTree) -> None:
        raise NotImplementedError("This method should be implemented by subclasses.")

    def get(self, data_type: str, start_time: datetime, end_time: datetime) -> xr.DataTree:
        raise NotImplementedError("This method should be implemented by subclasses.")


class IceChunkDataManager(DataManager):
    def __init__(self):
        super().__init__()

    def get_file_path(self, data_type :str, timestamp: datetime = None) -> str:
        return os.path.join(geode_config.data_lake.full_base_path,
                            f"{data_type}.icechunk")

    def put(self, data_type: str, data_tree: xr.DataTree) -> None:
        file_path = self.get_file_path(data_type)
        os.makedirs(os.path.dirname(file_path), exist_ok=True)

        storage = ic.local_filesystem_storage(file_path)
        repository_exists = ic.Repository.exists(storage)
        repo = ic.Repository.open_or_create(storage)

        if repository_exists:
            with repo.transaction("main", message=f"Append to {data_type}") as store:
                for node in data_tree.subtree:
                    dataset = node.to_dataset(inherit=False)

                    if "Location" not in dataset.dims:
                        continue

                    group = node.path.lstrip("/") or None

                    dataset.to_zarr(
                        store,
                        mode="a",
                        zarr_format=3,
                        group=group,
                        append_dim="Location",
                        consolidated=False,
                    )
        else:
            with repo.transaction("main", message=f"Create {data_type}") as store:
                data_tree.to_zarr(store, mode="w", zarr_format=3, consolidated=False)


class ZarrDataManager(DataManager):
    def __init__(self):
        super().__init__()

    def get_file_path(self, data_type :str, timestamp: datetime = None) -> str:
        if self.config.split_by == "none":
            return os.path.join(geode_config.data_lake.full_base_path,
                                f"{data_type}.zarr")

        assert timestamp is not None, "Timestamp must be provided for split_by option."
        year = timestamp.year
        month = timestamp.month
        day = timestamp.day

        if self.config.split_by == "year":
            return os.path.join(geode_config.data_lake.full_base_path,
                                f"{data_type}", f"{year}.zarr")
        elif self.config.split_by == "month":
            return os.path.join(geode_config.data_lake.full_base_path,
                                f"{data_type}", f"{year}_{month:02d}.zarr")
        elif self.config.split_by == "day":
            return os.path.join(geode_config.data_lake.full_base_path,
                                f"{data_type}", f"{year}_{month:02d}_{day:02d}.zarr")

    def put(self, data_type: str, data_tree: xr.DataTree) -> None:
        file_path = self.get_file_path(data_type)
        os.makedirs(os.path.dirname(file_path), exist_ok=True)

        # create the zarr store if it doesn't exist, otherwise open it in append mode
        if not os.path.exists(file_path):
            data_tree.to_zarr(file_path, mode='w', consolidated=True)
        else:
            data_tree.to_zarr(file_path, mode='a', append_dim='Location', consolidated=True)


class NetCDFDataManager(DataManager):
    def __init__(self):
        super().__init__()

    def get_file_path(self, data_type :str, timestamp: datetime = None) -> str:
        assert timestamp is not None, "Timestamp must be provided for split_by option."

        year = timestamp.year
        month = timestamp.month
        day = timestamp.day

        if self.config.split_by == "year":
            return os.path.join(geode_config.data_lake.full_base_path,
                                f"{data_type}", f"{year}.nc")
        elif self.config.split_by == "month":
            return os.path.join(geode_config.data_lake.full_base_path,
                                f"{data_type}", f"{year}_{month:02d}.nc")
        elif self.config.split_by == "day":
            return os.path.join(geode_config.data_lake.full_base_path,
                                f"{data_type}", f"{year}_{month:02d}_{day:02d}.nc")

    def put(self, data_type: str, data_tree: xr.DataTree, timestamp: datetime) -> None:
        file_path = self.get_file_path(data_type, timestamp)
        os.makedirs(os.path.dirname(file_path), exist_ok=True)

        # create the NetCDF file if it doesn't exist, otherwise open it in append mode
        if not os.path.exists(file_path):
            data_tree.to_netcdf(file_path, mode='w', format='NETCDF4')
        else:
            data_tree.to_netcdf(file_path, mode='a', format='NETCDF4')


manager_mapping = {
    "icechunk": IceChunkDataManager,
    "zarr": ZarrDataManager,
    "netcdf": NetCDFDataManager
}

def get_data_manager():
    data_manager_class = manager_mapping.get(geode_config.data_lake.type.lower())
    if data_manager_class is None:
        raise ValueError(f"Unsupported lake type: {geode_config.data_lake.type}")
    return data_manager_class()

data_manager = get_data_manager()