import os
from datetime import datetime
from typing import Any

import icechunk as ic
import numpy as np
import xarray as xr
import zarr

from geode.configs.geode_config import geode_config
from geode.data.filter.apply import apply
from geode.data.keys import LocationKey
from geode.data.manager.manager_base import DataManager


class AppendSchemaError(ValueError):
    """Raised when data to append does not have the variables already stored."""


def _check_append_schema(store: Any, data_tree: xr.DataTree, data_type: str) -> None:
    """Reject an append whose variables differ from what is stored.

    Appending along Location only extends the variables being written, so a variable
    missing from the new data stops growing and rows no longer line up. Check every
    group before writing any of them.
    """
    root = zarr.open_group(store, mode="r")
    for node in data_tree.subtree:
        dataset = node.to_dataset(inherit=False)
        if LocationKey not in dataset.dims:
            continue

        group = node.path.strip("/")
        if group and group not in root:
            raise AppendSchemaError(
                f"Cannot append to '{data_type}': group '{group}' is not in the store"
            )

        stored_group = root[group] if group else root
        stored = {name for name, _ in stored_group.arrays()}
        incoming = {str(name) for name in dataset.variables}
        if stored != incoming:
            raise AppendSchemaError(
                f"Cannot append to '{data_type}': group '{group or '/'}' differs from "
                f"the store. Missing from new data: {sorted(stored - incoming)}. "
                f"Not in store: {sorted(incoming - stored)}"
            )


def _has_data(repo: ic.Repository) -> bool:
    """Whether the repository holds data on main.

    The repository is created before the first write's transaction, so a write that
    is interrupted leaves an empty repository. That case is a new dataset, not an
    append.
    """
    try:
        root = zarr.open_group(repo.readonly_session("main").store, mode="r")
    except zarr.errors.GroupNotFoundError:
        return False
    return next(root.keys(), None) is not None


class IceChunkDataManager(DataManager):
    def __init__(self):
        super().__init__()

    def list_data_types(self) -> list[str]:
        base_path = geode_config.data_lake.full_base_path
        if not os.path.isdir(base_path):
            return []

        return sorted(
            entry.removesuffix(".icechunk")
            for entry in os.listdir(base_path)
            if entry.endswith(".icechunk")
            and os.path.isdir(os.path.join(base_path, entry))
        )

    def get_file_path(
        self,
        data_type: str,
        sub_type: str | None = None,
        timestamp: datetime | None = None,
    ) -> str:
        return os.path.join(
            geode_config.data_lake.full_base_path,
            f"{data_type}_{sub_type}.icechunk" if sub_type else f"{data_type}.icechunk",
        )

    def put(
        self, data_type: str, data_tree: xr.DataTree, sub_type: str | None = None
    ) -> None:
        file_path = self.get_file_path(data_type, sub_type)
        os.makedirs(os.path.dirname(file_path), exist_ok=True)

        storage = ic.local_filesystem_storage(file_path)
        repo = ic.Repository.open_or_create(storage)

        if _has_data(repo):
            with repo.transaction("main", message=f"Append to {data_type}") as store:
                _check_append_schema(store, data_tree, data_type)
                for node in data_tree.subtree:
                    dataset = node.to_dataset(inherit=False)

                    if LocationKey not in dataset.dims:
                        continue

                    group = node.path.lstrip("/") or None

                    dataset.to_zarr(
                        store,
                        mode="a",
                        zarr_format=3,
                        group=group,
                        append_dim=LocationKey,
                        consolidated=False,
                    )
        else:
            with repo.transaction("main", message=f"Create {data_type}") as store:
                data_tree.to_zarr(store, mode="w", zarr_format=3, consolidated=False)

    def get(
        self,
        data_type: str,
        start_time: np.datetime64,
        end_time: np.datetime64,
        filters: list[dict[str, Any]] | None = None,
    ) -> xr.DataTree:

        file_path = self.get_file_path(data_type)

        print("Getting data from file path:", file_path)

        storage = ic.local_filesystem_storage(file_path)
        repo = ic.Repository.open(storage)
        session = repo.readonly_session("main")

        datatree = xr.open_datatree(
            session.store,
            engine="zarr",
            consolidated=False,
            create_default_indexes=False,
        )

        datatree = apply(datatree, start_time, end_time, filters=filters)

        return datatree
