import argparse
import glob
import os
import sys
import warnings
from datetime import UTC, datetime, timedelta
from pathlib import Path

import netCDF4 as nc
import numpy as np
import xarray as xr
import yaml

from geode.data.data_manager import GEODEDataManager

warnings.filterwarnings(
    "ignore",
    message="Setting the shape on a NumPy array has been deprecated",
    category=DeprecationWarning,
)

"""
Usage:
python icechunk2ioda.py radiosonde 2026-09-15 2026-09-15
python icechunk2ioda.py iasi 2026-09-16 2026-09-16
"""

class IcechunkToIODAnetCDF:
    def __init__(
        self,
        data_type: str,
        output_file: str,
        start_window: datetime,
        end_window: datetime,
        debug: bool = False,
    ):
        self.data_type = data_type
        self.output_file = output_file
        self.start_window = start_window
        self.end_window = end_window
        self.debug = debug

    def _log_debug(self, msg: str):
        if self.debug:
            print(f"  [DEBUG] {msg}")

    def write_datatree_to_netcdf(self, data_tree: xr.DataTree, output_file: str):
        """
        Writes an xarray DataTree to a NetCDF4 file in a single write session,
        scoping dimensions to root and applying zlib compression to match IODA baseline files.
        """
        out_path = Path(output_file)
        out_path.parent.mkdir(parents=True, exist_ok=True)

        if out_path.exists():
            out_path.unlink()

        with nc.Dataset(output_file, "w", format="NETCDF4") as root:
            # 1. Define all dimensions at root level first
            for node in data_tree.subtree:
                dataset = node.to_dataset(inherit=False)
                for dim_name, dim_size in dataset.sizes.items():
                    if dim_name not in root.dimensions:
                        root.createDimension(dim_name, dim_size)

            # 2. Populate groups and variables
            for node in data_tree.subtree:
                group_path = node.path.lstrip("/")
                dataset = node.to_dataset(inherit=False)

                # Skip completely empty nodes (use .variables so coords aren't skipped)
                if len(dataset.variables) == 0:
                    continue

                if group_path:
                    grp = root
                    for part in group_path.split("/"):
                        if part not in grp.groups:
                            grp = grp.createGroup(part)
                        else:
                            grp = grp.groups[part]
                else:
                    grp = root

                # Write variables
                for var_name, var in dataset.variables.items():
                    data = np.asarray(var.values)

                    # Handle datetime64 -> int64 epoch seconds
                    if np.issubdtype(data.dtype, np.datetime64):
                        data = data.astype("datetime64[s]").astype(np.int64)
                        dtype = np.int64
                    elif (
                        data.dtype.kind in ("U", "S", "O")
                        or "str" in str(data.dtype).lower()
                        or "string" in str(data.dtype).lower()
                    ):
                        data = data.astype(object).astype(str)
                        dtype = str
                    else:
                        try:
                            dtype = data.dtype.newbyteorder("=")
                            data = np.ascontiguousarray(data, dtype=dtype)
                        except TypeError:
                            dtype = data.dtype
                            data = np.ascontiguousarray(data)

                    fill_val = var.encoding.get("_FillValue", None)
                    kwargs = {"fill_value": fill_val} if fill_val is not None else {}

                    # Apply DEFLATE compression on multidimensional numeric variables
                    if dtype != str and len(var.dims) > 0:
                        kwargs["zlib"] = True
                        kwargs["complevel"] = 4

                    nc_var = grp.createVariable(
                        var_name, dtype, var.dims, **kwargs
                    )

                    for attr_name, attr_val in var.attrs.items():
                        if attr_name != "_FillValue":
                            nc_var.setncattr(attr_name, attr_val)

                    nc_var[...] = data

    def convert(self) -> bool:
        print(f"  --> Fetching data via GEODE DataManager for type: {self.data_type}")

        try:
            # 1. GEODE DataManager API call
            geodedm = GEODEDataManager()
            datatree = geodedm.get(
                data_type=self.data_type,
                start_time=self.start_window,
                end_time=self.end_window,
            )

            # 2. Check observation count across subtree
            num_obs = 0
            for node in datatree.subtree:
                ds = node.to_dataset(inherit=False)
                if "Location" in ds.sizes:
                    num_obs = ds.sizes["Location"]
                    break

            print(f"      Filtering: Retained {num_obs} observations.")

            if num_obs == 0:
                print(
                    f"  [WARNING] 0 observations matched target time window ({self.start_window} to {self.end_window})."
                )
                return False

            self._log_debug(f"Loaded DataTree Summary:\n{datatree}")

            # 3. Export to NetCDF
            print(f"      Writing DataTree to IODA NetCDF: {self.output_file}")
            self.write_datatree_to_netcdf(datatree, self.output_file)
            return True

        except Exception as e:
            print(
                f"  [ERROR] Failed during GEODE/Icechunk conversion: {e}",
                file=sys.stderr,
            )
            if self.debug:
                import traceback

                traceback.print_exc()
            return False


def get_assimilation_window(
    cycle_date_str: str, cycle_hour: int
) -> tuple[datetime, datetime]:
    base_dt = datetime.strptime(cycle_date_str, "%Y-%m-%d").replace(tzinfo=UTC)

    if cycle_hour == 0:
        start_time = base_dt - timedelta(hours=3)
        end_time = base_dt + timedelta(hours=3)
    elif cycle_hour == 6:
        start_time = base_dt + timedelta(hours=3)
        end_time = base_dt + timedelta(hours=9)
    elif cycle_hour == 12:
        start_time = base_dt + timedelta(hours=9)
        end_time = base_dt + timedelta(hours=15)
    elif cycle_hour == 18:
        start_time = base_dt + timedelta(hours=15)
        end_time = base_dt + timedelta(hours=21)
    else:
        raise ValueError(f"Invalid cycle hour: {cycle_hour}. Must be 0, 6, 12, or 18.")

    return start_time, end_time


def print_netcdf_time_summary(output_pattern: str, debug: bool = False) -> None:
    print("\n--- Output NetCDF Time Summary ---")

    glob_pattern = output_pattern.replace("{splits/satId}", "*")
    matching_files = glob.glob(glob_pattern)

    if not matching_files:
        print(f"  No output files found matching pattern: {glob_pattern}")
        return

    for nc_file in matching_files:
        print(f"  File: {nc_file}")
        try:
            with nc.Dataset(nc_file, "r") as ds:
                if debug:
                    print(f"  [DEBUG] NetCDF Root Groups: {list(ds.groups.keys())}")

                dt_var = None
                if (
                    "MetaData" in ds.groups
                    and "dateTime" in ds.groups["MetaData"].variables
                ):
                    dt_var = ds.groups["MetaData"]["dateTime"][:]
                elif "dateTime" in ds.variables:
                    dt_var = ds.variables["dateTime"][:]

                if dt_var is not None and len(dt_var) > 0:
                    dt_vals = np.asarray(dt_var).ravel()

                    # Strip negative fill values (-9999) or extreme timestamps
                    valid_mask = (dt_vals > 0) & (dt_vals < 4102444800)
                    valid_ts = dt_vals[valid_mask]

                    if len(valid_ts) > 0:
                        timestamps = [
                            datetime.fromtimestamp(int(ts), tz=UTC)
                            for ts in valid_ts
                        ]

                        print(
                            f"    Min Obs Time : {min(timestamps).strftime('%Y-%m-%d %H:%M:%S UTC')}"
                        )
                        print(
                            f"    Max Obs Time : {max(timestamps).strftime('%Y-%m-%d %H:%M:%S UTC')}"
                        )
                        print(f"    Total Obs    : {len(valid_ts)}")
                    else:
                        print(
                            "    Total Obs    : 0 (File contains no valid observations inside time window)"
                        )
                else:
                    print(
                        "    MetaData/dateTime variable not found or empty in NetCDF file."
                    )
        except Exception as e:
            print(f"    Could not read NetCDF file: {e}")


def run_batch_conversion(
    data_type_id: str,
    start_date_str: str,
    end_date_str: str,
    config_path: str = "configs/icechunk2ioda.yaml",
    debug: bool = False,
):
    with open(config_path, "r") as f:
        config = yaml.safe_load(f)

    hours = config.get("hours", ["00", "06", "12", "18"])
    common = config.get("common", {})
    groups = config.get("groups", {})

    if data_type_id not in groups:
        available_groups = ", ".join(groups.keys())
        raise ValueError(
            f"Group '{data_type_id}' not found in '{config_path}'. "
            f"Available groups: {available_groups}"
        )

    group_cfg = groups[data_type_id]
    group_output_file = group_cfg.get("output_file", "gdas.t{hour}z.{id}.nc")
    target_items = group_cfg.get("items", [])

    start_date = datetime.strptime(start_date_str, "%Y-%m-%d").replace(tzinfo=UTC)
    end_date = datetime.strptime(end_date_str, "%Y-%m-%d").replace(tzinfo=UTC)

    for dt_config in target_items:
        sub_id = dt_config.get("id", data_type_id)
        print("\n==================================================")
        print(f"   Processing Data Sub-type: {sub_id}")
        print("==================================================")

        output_path = dt_config.get("output_path", common.get("output_path", ""))
        output_file_template = dt_config.get("output_file", group_output_file)

        if output_path and not output_path.startswith("/"):
            output_path = "/" + output_path

        current_date = start_date
        while current_date <= end_date:
            date_str = current_date.strftime("%Y%m%d")
            formatted_date = current_date.strftime("%Y-%m-%d")

            for hr in hours:
                cycle_hour = int(hr)
                hr_str = f"{cycle_hour:02d}"
                print(f"\n=== Processing Date/Cycle: {date_str} {hr_str}Z [{sub_id}] ===")

                eval_out_dir = output_path.replace("{hour}", hr_str).replace(
                    "{date}", date_str
                )
                if not os.path.exists(eval_out_dir):
                    print(f"  [INFO] Creating output directory: {eval_out_dir}")
                    os.makedirs(eval_out_dir, exist_ok=True)

                eval_out_file = (
                    output_file_template.replace("{hour}", hr_str)
                    .replace("{date}", date_str)
                    .replace("{id}", sub_id)
                )

                output_file = os.path.join(eval_out_dir, eval_out_file)

                start_window, end_window = get_assimilation_window(
                    formatted_date, cycle_hour
                )
                print(f"  [TIME WINDOW] Target range: {start_window} to {end_window}")

                converter = IcechunkToIODAnetCDF(
                    data_type=sub_id,
                    output_file=output_file,
                    start_window=start_window,
                    end_window=end_window,
                    debug=debug,
                )
                success = converter.convert()

                # Gracefully skip if 0 observations matched the cycle window
                if not success:
                    print(
                        f"  [INFO] Skipping cycle {date_str} {hr_str}Z [{sub_id}] - no observations to output."
                    )
                    continue

                print_netcdf_time_summary(output_file, debug=debug)

            current_date += timedelta(days=1)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Convert Icechunk repositories to IODA NetCDF format over a date range."
    )
    parser.add_argument(
        "data_type",
        type=str,
        help="Data type ID defined in config (e.g., iasi)",
    )
    parser.add_argument("start_date", type=str, help="Start date in YYYY-MM-DD format")
    parser.add_argument("end_date", type=str, help="End date in YYYY-MM-DD format")
    parser.add_argument(
        "--config",
        type=str,
        default="configs/icechunk2ioda.yaml",
        help="Path to YAML configuration file",
    )
    parser.add_argument(
        "--debug",
        action="store_true",
        help="Enable verbose debug logging and stack traces",
    )

    args = parser.parse_args()

    print(
        f"Starting conversion for data_type={args.data_type} from {args.start_date} to {args.end_date}"
    )
    if args.debug:
        print("[DEBUG] Debug logging enabled.")

    run_batch_conversion(
        args.data_type,
        args.start_date,
        args.end_date,
        config_path=args.config,
        debug=args.debug,
    )
    print("\nBatch conversion process complete!")
