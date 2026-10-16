import os
from datetime import UTC, datetime

import icechunk as ic
import numpy as np
import xarray as xr

from geode.configs.geode_config import geode_config

def select_datatree_variables(
    datatree: xr.DataTree,
    variables: list[str],
) -> xr.DataTree:
    selected = xr.DataTree(name=datatree.name)

    for path in variables:
        source_node = datatree[path]
        target_path = path.strip("/").split("/")

        current = selected
        for group in target_path[:-1]:
            if group not in current.children:
                current = current[group] = xr.DataTree(name=group)
            else:
                current = current[group]

        variable = target_path[-1]
        current.dataset = source_node.to_dataset()[[variable]]

    return selected


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
        vars: list[str] | None = None,
        filter: dict | None = None,
    ) -> xr.DataTree:
        raise NotImplementedError("This method should be implemented by subclasses.")


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
            # Append mode - variable schemas already exist in store
            with repo.transaction("main", message=f"Append to {data_type}") as store:
                for node in data_tree.subtree:
                    dataset = node.to_dataset(inherit=False)

                    if "Location" not in dataset.dims:
                        continue

                    # Cast string/character variables to object
                    for var_name in list(dataset.variables.keys()):
                        var = dataset.variables[var_name]
                        if var.dtype.kind in ("U", "S", "O"):
                            dataset[var_name] = var.astype(object)

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
            # Initial write - set variable-level encoding directly on DataArray.encoding
            with repo.transaction("main", message=f"Create {data_type}") as store:
                for node in data_tree.subtree:
                    dataset = node.to_dataset(inherit=False)

                    if "Location" not in dataset.dims:
                        continue

                    for var_name in list(dataset.variables.keys()):
                        var = dataset.variables[var_name]
                        if var.dtype.kind in ("U", "S", "O"):
                            # Cast variable to object
                            dataset[var_name] = var.astype(object)
                            # Set dtype object on DataArray encoding so xarray uses vlen string handling natively
                            dataset[var_name].encoding["dtype"] = "object"

                    group = node.path.lstrip("/") or None

                    dataset.to_zarr(
                        store,
                        mode="w",
                        zarr_format=3,
                        group=group,
                        consolidated=False,
                    )

    def get(
        self,
        data_type: str,
        start_time: datetime,
        end_time: datetime,
        vars: list[str] | None = None,
        filter: dict | None = None,
    ) -> xr.DataTree:

        file_path = self.get_file_path(data_type)
        print("Getting data from file path:", file_path)

        storage = ic.local_filesystem_storage(file_path)
        repo = ic.Repository.open(storage)
        session = repo.readonly_session("main")

        datatree = xr.open_datatree(
            session.store,
            engine="zarr",
            #            zarr_version=3,
            consolidated=False,
        )
        
        # 1. Safely locate dateTime variable across any group hierarchy
        dt_var = None
        for node in datatree.subtree:
            ds = node.to_dataset(inherit=False)
            if "dateTime" in ds.variables:
                dt_var = ds["dateTime"]
                break

        if dt_var is not None:
            dt_raw = np.asarray(dt_var.values)

            # Normalize timestamps to integer epoch seconds (handles datetime64, strings, or ns/s int64)
            if np.issubdtype(dt_raw.dtype, np.datetime64) or dt_raw.dtype.kind in ("U", "S", "O"):
                dt_secs = dt_raw.astype("datetime64[s]").astype(np.int64)
            else:
                dt_secs = dt_raw.astype(np.int64)
                valid_ts = dt_secs[(dt_secs > 0) & (dt_secs < 4102444800000000000)]
                if len(valid_ts) > 0 and valid_ts[0] > 1e16:
                    dt_secs = dt_secs // 1_000_000_000

            start_sec = int(start_time.astimezone(UTC).timestamp())
            end_sec = int(end_time.astimezone(UTC).timestamp())

            retained_indices = np.where((dt_secs >= start_sec) & (dt_secs < end_sec))[0]
            print(f"      [DataManager] Slicing: Retained {len(retained_indices)} / {len(dt_secs)} observations.")

            # 2. Eagerly slice each node and rebuild a concrete DataTree
            filtered_nodes = {}
            for path, node in datatree.subtree_with_keys:
                ds = node.to_dataset(inherit=False)
                if "Location" in ds.dims:
                    filtered_nodes[path] = ds.isel(Location=retained_indices).compute()
                else:
                    filtered_nodes[path] = ds.compute()

            datatree = xr.DataTree.from_dict(filtered_nodes)

        if vars is not None:
            datatree = select_datatree_variables(datatree, vars)

        return datatree

class ZarrDataManager(DataManager):
    def __init__(self):
        super().__init__()

    def list_data_types(self) -> list[str]:
        base_path = geode_config.data_lake.full_base_path
        if not os.path.isdir(base_path):
            return []

        if self.config.split_by == "none":
            return sorted(
                entry.removesuffix(".zarr")
                for entry in os.listdir(base_path)
                if entry.endswith(".zarr")
                and os.path.isdir(os.path.join(base_path, entry))
            )

        return sorted(
            entry
            for entry in os.listdir(base_path)
            if os.path.isdir(os.path.join(base_path, entry))
            and any(
                child.endswith(".zarr")
                and os.path.isdir(os.path.join(base_path, entry, child))
                for child in os.listdir(os.path.join(base_path, entry))
            )
        )

    def get_file_path(self, data_type: str, timestamp: datetime | None = None) -> str:
        if self.config.split_by == "none":
            return os.path.join(
                geode_config.data_lake.full_base_path, f"{data_type}.zarr"
            )

        assert timestamp is not None, "Timestamp must be provided for split_by option."
        year = timestamp.year
        month = timestamp.month
        day = timestamp.day

        if self.config.split_by == "year":
            return os.path.join(
                geode_config.data_lake.full_base_path, f"{data_type}", f"{year}.zarr"
            )
        elif self.config.split_by == "month":
            return os.path.join(
                geode_config.data_lake.full_base_path,
                f"{data_type}",
                f"{year}_{month:02d}.zarr",
            )
        elif self.config.split_by == "day":
            return os.path.join(
                geode_config.data_lake.full_base_path,
                f"{data_type}",
                f"{year}_{month:02d}_{day:02d}.zarr",
            )

    def put(
        self, data_type: str, data_tree: xr.DataTree, sub_type: str | None = None
    ) -> None:
        file_path = self.get_file_path(
            f"{data_type}_{sub_type}" if sub_type else data_type
        )
        os.makedirs(os.path.dirname(file_path), exist_ok=True)

        # create the zarr store if it doesn't exist, otherwise open it in append mode
        if not os.path.exists(file_path):
            data_tree.to_zarr(file_path, mode="w", consolidated=True)
        else:
            data_tree.to_zarr(
                file_path, mode="a", append_dim="Location", consolidated=True
            )


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


manager_mapping = {
    "icechunk": IceChunkDataManager,
    "zarr": ZarrDataManager,
    "netcdf": NetCDFDataManager,
}


def get_data_manager():
    data_manager_class = manager_mapping.get(geode_config.data_lake.type.lower())
    if data_manager_class is None:
        raise ValueError(f"Unsupported lake type: {geode_config.data_lake.type}")
    return data_manager_class()


data_manager = get_data_manager()
