#  Convert a single time window of GEODE Lake data to an IODA NetCDF file.

#  Usage:
#     python dev/ush/icechunk2ioda.py iasi_metop-b \
#         -s 2026-09-15T03:00:00 \
#         -e 2026-09-15T09:00:00 \
#         --clobber \
#         -o test_20261023_3.nc


import os

# Set Icechunk and Rust logging level to error before any libraries load
os.environ["ICECHUNK_LOG"] = "error"
os.environ["RUST_LOG"] = "error"

import argparse
import contextlib
import io
import re
import sys
import warnings
from datetime import UTC, datetime
from pathlib import Path

import numpy as np
import xarray as xr

from geode.data.data_manager import IceChunkDataManager

warnings.filterwarnings(
    "ignore",
    message="Setting the shape on a NumPy array has been deprecated",
    category=DeprecationWarning,
)


def format_ioda_datatree(datatree: xr.DataTree) -> xr.DataTree:
    """
    Formats the DataTree to strictly match the obsForge / IODA NetCDF convention:
      - Location and Channel are defined as root-level int32 dimension scales.
      - Child groups (MetaData, ObsValue) inherit root dimensions without local coordinates.
      - Group declaration order is preserved (MetaData first, then ObsValue).
    """
    num_locs = 0
    num_channels = None
    channel_vals = None

    for node in datatree.subtree:
        ds = node.to_dataset(inherit=False)
        if "Location" in ds.sizes and num_locs == 0:
            num_locs = ds.sizes["Location"]
        if "Channel" in ds.sizes and num_channels is None:
            num_channels = ds.sizes["Channel"]
            if "Channel" in ds.coords:
                channel_vals = ds.coords["Channel"].values
            elif "Channel" in ds.variables:
                channel_vals = ds["Channel"].values

    if channel_vals is None and num_channels is not None:
        channel_vals = np.arange(1, num_channels + 1, dtype=np.int32)
    elif channel_vals is not None:
        channel_vals = np.asarray(channel_vals, dtype=np.int32)

    # 1. Strip Location and Channel coordinates from all child groups
    for node in datatree.subtree:
        if node is not datatree:
            node.dataset = node.dataset.drop_vars(
                ["Location", "Channel"], errors="ignore"
            )

    # 2. Assign int32 dimension scale coordinates to the root group
    root_coords = {}
    if num_locs > 0:
        root_coords["Location"] = xr.DataArray(
            np.arange(num_locs, dtype=np.int32), dims=["Location"]
        )
    if num_channels is not None:
        root_coords["Channel"] = xr.DataArray(channel_vals, dims=["Channel"])

    saved_global_attrs = datatree.attrs.copy()
    datatree.dataset = datatree.dataset.assign_coords(root_coords)
    datatree.attrs.update(saved_global_attrs)
    datatree.dataset.attrs.update(saved_global_attrs)

    if "Location" in datatree.dataset:
        datatree.dataset["Location"].attrs.clear()
        datatree.dataset["Location"].encoding.update(
            {"dtype": "int32", "_FillValue": np.int32(2147483647)}
        )

    if "Channel" in datatree.dataset:
        datatree.dataset["Channel"].attrs.clear()
        datatree.dataset["Channel"].encoding.update(
            {"dtype": "int32", "_FillValue": np.int32(2147483647)}
        )

    # 3. Enforce canonical group order matching obsForge (MetaData, ObsValue, ...)
    preferred_order = ["MetaData", "ObsValue", "ObsError", "QualityMarker", "PreQC"]
    sorted_children = {}
    for grp in preferred_order:
        if grp in datatree.children:
            sorted_children[grp] = datatree.children[grp]
    for grp, child in datatree.children.items():
        if grp not in sorted_children:
            sorted_children[grp] = child

    out_tree = xr.DataTree(
        name=datatree.name, dataset=datatree.dataset, children=sorted_children
    )
    out_tree.attrs.update(saved_global_attrs)
    return out_tree


def write_datatree_to_netcdf(datatree: xr.DataTree, output_file: str, clobber: bool = False) -> None:
    """
    Writes DataTree using encoding parameters matching the obsForge IODA standard.

    Parameters
    ----------
    datatree : xr.DataTree
        The populated DataTree to write.
    output_file : str
        Target NetCDF file path.
    clobber : bool, default False
        Whether to overwrite an existing output file.
    """
    out_path = Path(output_file)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    if out_path.exists():
        if not clobber:
            raise FileExistsError(
                f"Output file '{out_path}' already exists. Use '--clobber' (-c) to overwrite."
            )
        out_path.unlink()

    datatree = format_ioda_datatree(datatree)

    for node in datatree.subtree:
        ds = node.to_dataset(inherit=False)

        for name in list(ds.variables.keys()):
            var = ds.variables[name]

            # Strip Zarr/Icechunk specific chunk/filter keys
            for key in ("chunks", "preferred_chunks", "compressor", "filters"):
                node[name].encoding.pop(key, None)

            existing_fill = var.encoding.get("_FillValue", var.attrs.get("_FillValue"))

            if name == "dateTime":
                # Convert datetime64 directly to int64 epoch seconds to bypass Xarray's CF coder
                if np.issubdtype(node[name].dtype, np.datetime64):
                    secs = node[name].values.astype("datetime64[s]").astype(np.int64)
                    attrs = node[name].attrs.copy()
                    attrs["long_name"] = "Datetime"
                    attrs["units"] = "seconds since 1970-01-01T00:00:00Z"
                    attrs.pop("calendar", None)

                    node[name] = xr.DataArray(
                        secs,
                        dims=node[name].dims,
                        attrs=attrs,
                    )
                else:
                    node[name].attrs["units"] = "seconds since 1970-01-01T00:00:00Z"
                    node[name].attrs.pop("calendar", None)

                node[name].encoding = {
                    "dtype": "int64",
                    "_FillValue": np.int64(
                        existing_fill
                        if existing_fill is not None
                        else 9223372036854775807
                    ),
                }

            # Preserve numeric encodings and compression
            elif (
                var.ndim > 0
                and var.dtype.kind in "biuf"
                and name not in ("Location", "Channel")
            ):
                zlib = var.encoding.get("zlib", True)
                complevel = var.encoding.get("complevel", 4)

                encoding_update = {
                    "zlib": zlib,
                    "complevel": complevel,
                }
                if existing_fill is not None:
                    encoding_update["_FillValue"] = existing_fill

                node[name].encoding.update(encoding_update)

    datatree.to_netcdf(output_file, engine="netcdf4")


def parse_iso_datetime(dt_str: str) -> datetime:
    """Parses ISO-8601 string or standard YYYY-MM-DD[THH:MM:SS] to UTC datetime."""
    dt = datetime.fromisoformat(dt_str)
    return dt if dt.tzinfo else dt.replace(tzinfo=UTC)


def convert_single_window(
    data_type: str,
    start_time: datetime,
    end_time: datetime,
    output_file: str,
    clobber: bool = False,
    debug: bool = False,
) -> bool:
    """Core function to convert one time window for one observation type."""
    out_path = Path(output_file)
    if out_path.exists() and not clobber:
        print(
            f"[ERROR] Output file '{out_path}' already exists. "
            "Pass '--clobber' (-c) to overwrite.",
            file=sys.stderr,
        )
        return False

    print(f"--> Fetching data via IceChunkDataManager for type: {data_type}")
    print(f"    Window: {start_time} to {end_time}")

    dm = IceChunkDataManager()

    # Capture stdout from data_manager.py to hide raw print(time_mask) array
    stdout_buf = io.StringIO()
    with contextlib.redirect_stdout(stdout_buf):
        datatree = dm.get(
            data_type=data_type,
            start_time=start_time,
            end_time=end_time,
        )

    captured_output = stdout_buf.getvalue()

    # Extract total observations from captured output
    total_obs = None
    match = (
        re.search(r"Location[^\d]*(\d+)", captured_output)
        or re.search(r"shape=\((\d+)", captured_output)
        or re.search(r"(\d+)\s+observations", captured_output)
        or re.search(r"\b(\d{6,8})\b", captured_output)
    )
    if match:
        total_obs = int(match.group(1))

    for line in captured_output.splitlines():
        if line.startswith("Getting data from file path:"):
            print(f"    {line}")
        elif debug:
            print(f"    [dm debug] {line}")

    num_obs = 0
    for node in datatree.subtree:
        ds = node.to_dataset(inherit=False)
        if "Location" in ds.sizes:
            num_obs = ds.sizes["Location"]
            break

    if total_obs is not None:
        print(f"    Retained {num_obs} / {total_obs} observations")
    else:
        print(f"    Retained observations: {num_obs}")

    if num_obs == 0:
        print("[WARNING] 0 observations matched target time window.")
        return False

    if debug:
        print(f"  [DEBUG] DataTree summary:\n{datatree}")

    print(f"--> Writing DataTree to NetCDF via Xarray: {output_file}")
    write_datatree_to_netcdf(datatree, output_file, clobber=clobber)
    print("Conversion completed successfully.")
    return True


def main():
    parser = argparse.ArgumentParser(
        description="Convert a single time window of GEODE Lake data to an IODA NetCDF file."
    )
    parser.add_argument(
        "data_type",
        type=str,
        help="Observation sub-type identifier (e.g., radiosonde, iasi_metop-b, atms_npp)",
    )
    parser.add_argument(
        "-s",
        "--start-time",
        type=str,
        required=True,
        help="Window start in ISO format (e.g., 2026-09-14T21:00:00)",
    )
    parser.add_argument(
        "-e",
        "--end-time",
        type=str,
        required=True,
        help="Window end in ISO format (e.g., 2026-09-15T03:00:00)",
    )
    parser.add_argument(
        "-o",
        "--output",
        type=str,
        required=True,
        help="Full path for the output NetCDF file",
    )
    parser.add_argument(
        "-c",
        "--clobber",
        action="store_true",
        help="Overwrite output file if it already exists",
    )
    parser.add_argument(
        "--debug",
        action="store_true",
        help="Enable verbose debug logging",
    )

    args = parser.parse_args()

    start_window = parse_iso_datetime(args.start_time)
    end_window = parse_iso_datetime(args.end_time)

    success = convert_single_window(
        data_type=args.data_type,
        start_time=start_window,
        end_time=end_window,
        output_file=args.output,
        clobber=args.clobber,
        debug=args.debug,
    )

    if not success:
        sys.exit(1)


if __name__ == "__main__":
    main()
