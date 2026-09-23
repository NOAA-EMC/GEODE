from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import icechunk
import numpy as np
import xarray as xr
import zarr


def json_attrs(attrs: dict[str, Any]) -> dict[str, Any]:
    """Convert NumPy values in attributes to JSON-compatible values."""
    result = {}
    for key, value in attrs.items():
        if isinstance(value, np.ndarray):
            result[key] = value.tolist()
        elif isinstance(value, np.generic):
            result[key] = value.item()
        else:
            result[key] = value
    return result


class IcechunkDataStore:
    """Scientific data store backed by an Icechunk repository."""

    def __init__(self, repository: str | Path):
        self.repository = Path(repository)
        storage = icechunk.local_filesystem_storage(str(self.repository))
        self.repo = icechunk.Repository.open_or_create(storage)

    def register_netcdf(
        self,
        nc_path: str | Path,
        address: str,
    ) -> None:
        """Copy an IODA NetCDF product into the Icechunk store."""
        nc_path = Path(nc_path)

        # ------------------------------------------------------------
        # 1. Read everything from NetCDF while outside the transaction.
        # ------------------------------------------------------------

        with xr.open_dataset(
            nc_path,
            decode_times=False,
        ) as ds:
            root_attrs = json_attrs(dict(ds.attrs))

        groups = {}

        for group_name in [
            "MetaData",
            "ObsValue",
            "ObsError",
            "PreQC",
            "ObsType",
        ]:
            try:
                with xr.open_dataset(
                    nc_path,
                    group=group_name,
                    decode_times=False,
                ) as group_ds:

                    variables = {}

                    for name, variable in group_ds.variables.items():
                        if variable.ndim != 1:
                            continue

                        print(
                            f"  reading {group_name}/{name}: "
                            f"dtype={variable.dtype}, shape={variable.shape}",
                            flush=True,
                        )

                        data = variable.values.copy()

                        if data.dtype == object:
                            print(
                                f"    skipping object variable: {name}",
                                flush=True,
                            )
                            continue

                        variables[name] = (
                            data,
                            json_attrs(dict(variable.attrs)),
                            list(variable.dims),
                        )

                    groups[group_name] = variables

            except (OSError, KeyError):
                continue

            variables_by_group = {
                group_name: list(variables)
                for group_name, variables in groups.items()
            }

        # ------------------------------------------------------------
        # 2. Write the already-loaded data to Icechunk.
        # ------------------------------------------------------------

        with self.repo.transaction(
            "main",
            message=f"register {address}",
        ) as zstore:

            root = zarr.open_group(zstore)

            if address in root:
                del root[address]

            product_group = root.create_group(address)
            product_group.attrs.update(root_attrs)

            for group_name, variables in groups.items():

                zgroup = product_group.create_group(group_name)

                for name, (data, attrs, dims) in variables.items():

                    print(
                        f"  writing {group_name}/{name}",
                        flush=True,
                    )

                    array = zgroup.create_array(
                        name,
                        data=data,
                        overwrite=True,
                    )

                    array.attrs.update(attrs)
                    array.attrs["_ARRAY_DIMENSIONS"] = dims

        return {
            "variables": variables_by_group,
        }

    def list_products(self) -> list[str]:
        """Return the data products stored at the repository root."""
        session = self.repo.readonly_session(branch="main")
        root = zarr.open_group(session.store, mode="r")
        return sorted(root.group_keys())

    def metadata(self, address: str) -> dict[str, Any]:
        """
        Inspect the stored data product and return standardized spatial,
        temporal, and attribute metadata.
        """
        session = self.repo.readonly_session(branch="main")
        root = zarr.open_group(session.store, mode="r")

        if address not in root:
            raise KeyError(f"No data product stored at '{address}'")

        group = root[address]
        attrs = dict(group.attrs)

        # 1. Derive Temporal Extent
        start_dt = None
        end_dt = None

        if "datetimeRange" in attrs:
            start_dt = datetime.fromtimestamp(
                int(attrs["datetimeRange"][0]), tz=timezone.utc
            )
            end_dt = datetime.fromtimestamp(
                int(attrs["datetimeRange"][1]), tz=timezone.utc
            )
        elif "MetaData" in group and "dateTime" in group["MetaData"]:
            time_arr = group["MetaData"]["dateTime"][:]
            valid_times = time_arr[time_arr > 0]
            if len(valid_times) > 0:
                start_dt = datetime.fromtimestamp(
                    int(valid_times.min()), tz=timezone.utc
                )
                end_dt = datetime.fromtimestamp(
                    int(valid_times.max()), tz=timezone.utc
                )

        if start_dt is None:
            raise ValueError(
                f"Cannot determine temporal extent for '{address}'"
            )

        # 2. Derive Spatial Extent
        bbox = [-180.0, -90.0, 180.0, 90.0]
        geometry = None

        if (
            "MetaData" in group
            and "latitude" in group["MetaData"]
            and "longitude" in group["MetaData"]
        ):
            lats = group["MetaData"]["latitude"][:]
            lons = group["MetaData"]["longitude"][:]

            valid_mask = (
                (lats >= -90.0)
                & (lats <= 90.0)
                & (lons >= -180.0)
                & (lons <= 180.0)
            )
            valid_lats = lats[valid_mask]
            valid_lons = lons[valid_mask]

            if len(valid_lats) > 0 and len(valid_lons) > 0:
                min_lat, max_lat = float(valid_lats.min()), float(valid_lats.max())
                min_lon, max_lon = float(valid_lons.min()), float(valid_lons.max())

                bbox = [min_lon, min_lat, max_lon, max_lat]
                geometry = {
                    "type": "Polygon",
                    "coordinates": [[
                        [min_lon, min_lat],
                        [max_lon, min_lat],
                        [max_lon, max_lat],
                        [min_lon, max_lat],
                        [min_lon, min_lat],
                    ]],
                }

        return {
            "address": address,
            "start_datetime": start_dt,
            "end_datetime": end_dt,
            "bbox": bbox,
            "geometry": geometry,
            "attributes": attrs,
        }

    def open_dataset(
        self,
        address: str,
        group: str | None = None,
        branch: str = "main",
    ) -> dict[str, xr.Dataset]:
        """Open a stored product from an Icechunk session as xarray Datasets."""
        session = self.repo.readonly_session(branch=branch)
        target_path = group if group is not None else f"/{address}"

        zroot = zarr.open_group(session.store, path=target_path, mode="r")

        datasets = {}
        for sub_group_name in zroot.group_keys():
            zsub = zroot[sub_group_name]

            data_vars = {}
            for var_name in zsub.array_keys():
                zarr_arr = zsub[var_name]
                dims = zarr_arr.attrs.get("_ARRAY_DIMENSIONS", ["Location"])
                data_vars[var_name] = (dims, zarr_arr[:], dict(zarr_arr.attrs))

            datasets[sub_group_name] = xr.Dataset(
                data_vars=data_vars,
                attrs=dict(zsub.attrs),
            )

        return datasets

    def location(self, address: str) -> str:
        """Return the external repository URI."""
        return str(self.repository.resolve())
