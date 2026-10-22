from datetime import UTC, datetime
import xarray as xr
from typing import Any

from geode.configs.geode_config import geode_config


class DataManager:
    def __init__(self):
        self.config = geode_config.data_lake

    def list_data_types(self) -> list[str]:
        raise NotImplementedError("This method should be implemented by subclasses.")

    def get_file_path(
        self,
        data_type: str,
        sub_type: str | None = None,
        timestamp: datetime | None = None,
    ) -> str:
        raise NotImplementedError("This method should be implemented by subclasses.")

    def put(
        self,
        data_type: str,
        data_tree: xr.DataTree,
        sub_type: str | None = None,
    ) -> None:
        raise NotImplementedError("This method should be implemented by subclasses.")

    def get(
        self,
        data_type: str,
        start_time: datetime,
        end_time: datetime,
        filters: list[dict[str, Any]] | None = None,
    ) -> xr.DataTree:

        raise NotImplementedError("This method should be implemented by subclasses.")
