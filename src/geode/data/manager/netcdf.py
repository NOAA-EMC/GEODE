import os

from datetime import datetime

import xarray as xr

from geode.configs.geode_config import geode_config
from geode.data.manager.manager_base import DataManager


class NetCDFDataManager(DataManager):
    def __init__(self):
        super().__init__()

    def list_data_types(self) -> list[str]:
        base_path = geode_config.data_lake.full_base_path
        if not os.path.isdir(base_path):
            return []

        return sorted(
            entry
            for entry in os.listdir(base_path)
            if os.path.isdir(os.path.join(base_path, entry))
            and any(
                child.endswith(".nc")
                and os.path.isfile(os.path.join(base_path, entry, child))
                for child in os.listdir(os.path.join(base_path, entry))
            )
        )

    def get_file_path(self, data_type: str, timestamp: datetime | None = None) -> str:
        assert timestamp is not None, "Timestamp must be provided for split_by option."

        year = timestamp.year
        month = timestamp.month
        day = timestamp.day

        if self.config.split_by == "year":
            return os.path.join(
                geode_config.data_lake.full_base_path, f"{data_type}", f"{year}.nc"
            )
        elif self.config.split_by == "month":
            return os.path.join(
                geode_config.data_lake.full_base_path,
                f"{data_type}",
                f"{year}_{month:02d}.nc",
            )
        elif self.config.split_by == "day":
            return os.path.join(
                geode_config.data_lake.full_base_path,
                f"{data_type}",
                f"{year}_{month:02d}_{day:02d}.nc",
            )

    def put(
        self,
        data_type: str,
        data_tree: xr.DataTree,
        timestamp: datetime,
        sub_type: str | None = None,
    ) -> None:
        file_path = self.get_file_path(
            f"{data_type}_{sub_type}" if sub_type else data_type, timestamp
        )
        os.makedirs(os.path.dirname(file_path), exist_ok=True)

        # create the NetCDF file if it doesn't exist, otherwise open it in append mode
        if not os.path.exists(file_path):
            data_tree.to_netcdf(file_path, mode="w", format="NETCDF4")
        else:
            data_tree.to_netcdf(file_path, mode="a", format="NETCDF4")
