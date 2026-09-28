#!/usr/bin/env python3

import sys

import xarray as xr
import icechunk
import zarr
import netCDF4


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
    nc.close()

    # Copy each IODA group.
    for group_name in GROUPS:
        if group_name not in available_groups:
            print(f"Skipping {group_name}: not present")
            continue

        print(f"Reading {group_name}")

        ds = xr.open_dataset(input_file, group=group_name)

        group = root.create_group(group_name)

        for name, variable in ds.data_vars.items():
            print(f"  {name}: {variable.dtype} {variable.shape}")

            group.create_array(
                name,
                data=variable.values,
                chunks=variable.encoding.get("chunksizes"),
            )

            # Copy JSON-compatible attributes.
            for key, value in variable.attrs.items():
                try:
                    group[name].attrs[key] = value
                except Exception:
                    print(f"    skipping attribute {key}")

        ds.close()

    session.commit("import IODA NetCDF dataset")

    print(f"\nWritten: {output_store}")


if __name__ == "__main__":
    main()
