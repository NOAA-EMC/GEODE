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
python dev/ush/icechunk2ioda.py iasi_metop-b \
        -s 2026-09-15T03:00:00 \
        -e 2026-09-15T09:00:00 \
        -o /path/to/output/gdas.t06z.radiance_iasi_metop-b.nc
"""


def write_datatree_to_netcdf(datatree: xr.DataTree, output_file: str) -> None:
    """
    Writes DataTree using encoding parameters read directly from the GEODE dataset,
    falling back to standard IODA defaults if not defined.
    """
    out_path = Path(output_file)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    if out_path.exists():
        out_path.unlink()

    for node in datatree.subtree:
        ds = node.to_dataset(inherit=False)

        for name, var in ds.variables.items():
            # 1. Read existing encoding/attrs or fall back to IODA standards
            existing_dtype = var.encoding.get("dtype", var.dtype)
            existing_fill = var.encoding.get("_FillValue", var.attrs.get("_FillValue"))

            if name == "dateTime":
                # Read time units and calendar from dataset if present
                units = (
                    var.encoding.get("units")
                    or var.attrs.get("units")
                    or "seconds since 1970-01-01T00:00:00Z"
                )
                # IODA/JEDI standard requires 'Z' rather than '+00:00'
                units = str(units).replace("+00:00", "Z")

                calendar = (
                    var.encoding.get("calendar")
                    or var.attrs.get("calendar")
                    or "proleptic_gregorian"
                )

                # Use int64 max fallback matching GEODE Lake convention
                fill_val = (
                    existing_fill
                    if existing_fill is not None
                    else np.iinfo(np.int64).max
                )

                node[name].encoding.update(
                    {
                        "dtype": "int64",
                        "units": units,
                        "calendar": calendar,
                        "_FillValue": np.int64(fill_val),
                    }
                )

            # Numeric whitelist avoids crashing on NumPy 2.0 StringDType (kind='T')
            elif var.ndim > 0 and var.dtype.kind in "biuf":
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
