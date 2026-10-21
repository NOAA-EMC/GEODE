import argparse
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

"""
usage
python test/icechunk2ioda.py iasi_metop-b -s 2026-09-15T03:00:00 -e 2026-09-15T09:00:00 -o /path/to/output/gdas.t06z.radiance_iasi_metop-b.nc
"""


def write_datatree_to_netcdf(datatree: xr.DataTree, output_file: str) -> None:
    """Writes DataTree using Xarray to_netcdf with compression."""
    for node in datatree.subtree:
        ds = node.to_dataset(inherit=False)

        if "dateTime" in ds.variables:
            ds["dateTime"].encoding = {
                "dtype": "int64",
                "units": "seconds since 1970-01-01T00:00:00Z",
                "calendar": "proleptic_gregorian",
                "_FillValue": np.int64(np.iinfo(np.int64).max),
            }

        for name, var in ds.variables.items():
            if name != "dateTime" and var.ndim > 0 and var.dtype.kind not in ("U", "S", "O"):
                var.encoding = {"zlib": True, "complevel": 4,
                                "_FillValue": var.encoding.get("_FillValue")}

        node.dataset = ds

    datatree.to_netcdf(output_file, engine="netcdf4")


def parse_iso_datetime(dt_str: str) -> datetime:
    """Parses ISO-8601 string or standard YYYY-MM-DD[THH:MM:SS] to UTC datetime."""
    dt = datetime.fromisoformat(dt_str.replace("Z", "+00:00"))
    return dt if dt.tzinfo else dt.replace(tzinfo=UTC)


def convert_single_window(
    data_type: str,
    start_time: datetime,
    end_time: datetime,
    output_file: str,
    debug: bool = False,
) -> bool:
    """Core function to convert one time window for one observation type."""
    print(f"--> Fetching data via IceChunkDataManager for type: {data_type}")
    print(f"    Window: {start_time} to {end_time}")

    dm = IceChunkDataManager()
    datatree = dm.get(
        data_type=data_type,
        start_time=start_time,
        end_time=end_time,
    )

#    dt = datatree["MetaData"]["dateTime"]
#    print(dt.dtype, dt.attrs, dt.encoding)


    num_obs = 0
    for node in datatree.subtree:
        ds = node.to_dataset(inherit=False)
        if "Location" in ds.sizes:
            num_obs = ds.sizes["Location"]
            break

    print(f"    Retained observations: {num_obs}")

    if num_obs == 0:
        print("[WARNING] 0 observations matched target time window.")
        return False

    if debug:
        print(f"  [DEBUG] DataTree summary:\n{datatree}")

    print(f"--> Writing DataTree to NetCDF via Xarray: {output_file}")
    write_datatree_to_netcdf(datatree, output_file)
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
        debug=args.debug,
    )

    if not success:
        sys.exit(1)


if __name__ == "__main__":
    main()
