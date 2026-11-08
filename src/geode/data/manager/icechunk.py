import os
from datetime import datetime
from typing import Any

import icechunk as ic
import numpy as np
import xarray as xr

from geode.configs.geode_config import geode_config
from geode.data.filter.apply import apply
from geode.data.keys import LocationKey
from geode.data.manager.manager_base import DataManager


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
        repository_exists = ic.Repository.exists(storage)
        repo = ic.Repository.open_or_create(storage)

        if repository_exists:
            with repo.transaction("main", message=f"Append to {data_type}") as store:
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

        # Inspect group metadata without loading array data.
        raw_tree = xr.open_datatree(
            session.store,
            engine="zarr",
            consolidated=False,
            create_default_indexes=False,
            decode_times=False,
            mask_and_scale=False,
        )

        group_options = {}

        for node in raw_tree.subtree:
            ds = node.to_dataset(inherit=False)
            mask_options = {}

            for name, var in ds.variables.items():
                fill_value = var.attrs.get("_FillValue")
                units = var.attrs.get("units", "")

                # Preserve integer variables and their integer fill values.
                # Leave CF time variables under normal mask/scale decoding.
                if (
                    np.issubdtype(var.dtype, np.integer)
                    and isinstance(fill_value, (int, np.integer))
                    and " since " not in units
                ):
                    mask_options[name] = False

            group_options[node.path] = mask_options

        raw_tree.close()

        # Open each group separately so masking options are group-specific.
        datasets = {}

        for group, mask_options in group_options.items():
            datasets[group] = xr.open_dataset(
                session.store,
                engine="zarr",
                group=group.lstrip("/") or None,
                consolidated=False,
                create_default_indexes=False,
                mask_and_scale=mask_options,
            )

        datatree = xr.DataTree.from_dict(datasets)

        datatree = apply(datatree, start_time, end_time, filters=filters)

        return datatree
