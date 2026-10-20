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
    """Writes DataTree using native Xarray to_netcdf with zlib compression."""
    for node in datatree.subtree:
        ds = node.to_dataset(inherit=False)
        for var_name, var in ds.variables.items():
            if var_name == "dateTime":
                if np.issubdtype(var.dtype, np.datetime64):
                    node[var_name] = var.astype("datetime64[s]").astype(np.int64)
                elif var.dtype.kind in ("i", "u"):
                    vals = np.asarray(var.values).ravel()
                    valid = vals[(vals > 0) & (vals < 4102444800000000000)]
                    if len(valid) > 0 and valid[0] > 1e16:
                        node[var_name] = (var // 1_000_000_000).astype(np.int64)

                node[var_name].attrs.pop("units", None)
                node[var_name].attrs.pop("calendar", None)
                node[var_name].encoding["dtype"] = "int64"

            if var.ndim > 0 and var.dtype.kind not in ("U", "S", "O"):
                node[var_name].encoding["zlib"] = True
                node[var_name].encoding["complevel"] = 4

    out_path = Path(output_file)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    if out_path.exists():
        out_path.unlink()

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
