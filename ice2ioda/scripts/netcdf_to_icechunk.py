#!/usr/bin/env python3

import sys

import xarray as xr
import icechunk
import zarr
import netCDF4
import numpy as np


GROUPS = [
    "MetaData",
    "ObsValue",
    "ObsError",
    "PreQC",
]


def main():
    if len(sys.argv) != 3:
        print(f"usage: {sys.argv[0]} INPUT.nc OUTPUT.icechunk")
        sys.exit(1)

    input_file = sys.argv[1]
    output_store = sys.argv[2]

    storage = icechunk.local_filesystem_storage(output_store)
    repo = icechunk.Repository.create(storage)
    session = repo.writable_session("main")

    root = zarr.open_group(session.store, mode="w")

    # Copy the root attributes.
    root_ds = xr.open_dataset(input_file)

    for key, value in root_ds.attrs.items():
        # Icechunk/Zarr requires JSON-compatible attributes.
        if isinstance(value, (str, int, float, bool)):
            root.attrs[key] = value
        elif isinstance(value, (list, tuple)):
            root.attrs[key] = list(value)

    root_ds.close()

    nc = netCDF4.Dataset(input_file)
    available_groups = set(nc.groups)

    # Copy each IODA group.
    for group_name in GROUPS:
        if group_name not in available_groups:
            print(f"Skipping {group_name}: not present")
            continue

        print(f"Reading {group_name}")

        ds = xr.open_dataset(input_file, group=group_name)
        nc_group = netCDF4.Dataset(input_file, "r").groups[group_name]

        group = root.create_group(group_name)

        for name, variable in ds.data_vars.items():
            nc_variable = nc_group.variables[name]

            # data = nc_variable[:]

            # if isinstance(data, np.ma.MaskedArray):
                # fill_value = nc_variable.getncattr("_FillValue")
                # print(f"WARNING: {name} has masked values; filling with {fill_value}")
                # data = data.filled(fill_value)

            fill_value = None

            if "_FillValue" in nc_variable.ncattrs():
                fill_value = nc_variable.getncattr("_FillValue")

            data = nc_variable[:]

            if isinstance(data, np.ma.MaskedArray):
                if fill_value is None:
                    raise RuntimeError(
                        f"{group_name}/{name}: masked data but no _FillValue"
                    )

                print(
                    f"WARNING: {group_name}/{name} has masked values; "
                    f"filling with {fill_value}"
                )
                data = data.filled(fill_value)

            print(
                f"  {name}: "
                f"{nc_variable.dtype} {nc_variable.shape}"
            )

            group.create_array(
                name,
                data=data,
                chunks=nc_variable.chunking()
                if nc_variable.chunking() != "contiguous"
                else None,
            )

            # Copy JSON-compatible attributes.
            for key, value in variable.attrs.items():
                try:
                    group[name].attrs[key] = value
                except Exception:
                    print(f"    skipping attribute {key}")

        nc_group = None
        ds.close()

    nc.close()
    session.commit("import IODA NetCDF dataset")

    print(f"\nWritten: {output_store}")


if __name__ == "__main__":
    main()
