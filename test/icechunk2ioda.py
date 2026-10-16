import argparse
import glob
import os
import sys
import warnings
from datetime import UTC, datetime, timedelta
from pathlib import Path

import icechunk as ic
import netCDF4 as nc
import numpy as np
import xarray as xr
import yaml

from geode.data.data_manager import IceChunkDataManager

warnings.filterwarnings(
    "ignore",
    message="Setting the shape on a NumPy array has been deprecated",
    category=DeprecationWarning,
)

"""
usage:
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
        Writes an xarray DataTree to a NetCDF4 file by opening the file once
        and writing all groups directly, avoiding repeated open/close/lock cycles.
        """
        out_path = Path(output_file)
        out_path.parent.mkdir(parents=True, exist_ok=True)

        if out_path.exists():
            out_path.unlink()

        with nc.Dataset(output_file, "w", format="NETCDF4") as root:
            for node in data_tree.subtree:
                group_path = node.path.lstrip("/")
                dataset = node.to_dataset(inherit=False)

                if len(dataset.data_vars) == 0:
                    continue

                # Navigate/create the group hierarchy
                if group_path:
                    grp = root
                    for part in group_path.split("/"):
                        if part not in grp.groups:
                            grp = grp.createGroup(part)
                        else:
                            grp = grp.groups[part]
                else:
                    grp = root

                # Create dimensions using dataset.sizes (fixes Xarray deprecation warning)
                for dim_name, dim_size in dataset.sizes.items():
                    if dim_name not in grp.dimensions:
                        grp.createDimension(dim_name, dim_size)

                # Write variables
                for var_name, var in dataset.variables.items():
                    data = np.asarray(var.values)

                    # Handle datetime64 -> int64 epoch seconds
                    if np.issubdtype(data.dtype, np.datetime64):
                        data = data.astype("datetime64[s]").astype(np.int64)
                        dtype = np.int64
                    elif (data.dtype.kind in ("U", "S", "O") or
                        "str" in str(data.dtype).lower() or
                        "string" in str(data.dtype).lower()):
                        # Convert via object to handle NumPy 2.0 StringDType
                        data = data.astype(object).astype(str)
                        dtype = str
                    else:
                        try:
                            dtype = data.dtype.newbyteorder("=")
                            data = np.ascontiguousarray(data, dtype=dtype)
                        except TypeError:
                            # Fallback for new-style NumPy dtypes that don't support newbyteorder
                            dtype = data.dtype
                            data = np.ascontiguousarray(data)

                    fill_val = var.encoding.get("_FillValue", None)
                    kwargs = {"fill_value": fill_val} if fill_val is not None else {}

                    nc_var = grp.createVariable(
                        var_name, dtype, var.dims, **kwargs
                    )

                    for attr_name, attr_val in var.attrs.items():
                        if attr_name != "_FillValue":
                            nc_var.setncattr(attr_name, attr_val)

                    nc_var[...] = data


                '''
                for var_name, var in dataset.variables.items():
                    data = np.asarray(var.values)

                    # Handle datetime64 -> int64 epoch seconds
                    if np.issubdtype(data.dtype, np.datetime64):
                        data = data.astype("datetime64[s]").astype(np.int64)
                        dtype = np.int64
                    elif data.dtype.kind == "U" or data.dtype == object:
                        # Variable-length strings
                        dtype = str
                    else:
                        dtype = data.dtype.newbyteorder("=")
                        data = np.ascontiguousarray(data, dtype=dtype)

                    fill_val = var.encoding.get("_FillValue", None)
                    kwargs = {"fill_value": fill_val} if fill_val is not None else {}

                    nc_var = grp.createVariable(
                        var_name, dtype, var.dims, **kwargs
                    )

                    for attr_name, attr_val in var.attrs.items():
                        if attr_name != "_FillValue":
                            nc_var.setncattr(attr_name, attr_val)

                    nc_var[...] = data
                '''

    def convert(self) -> bool:
        print(f"  --> Fetching data via GEODE DataManager for type: {self.data_type}")

        try:
            # 1. Initialize GEODE DataManager to get the repository path
            dm = IceChunkDataManager()
            file_path = dm.get_file_path(self.data_type)

            print(f"      Opening Icechunk store from: {file_path}")
            storage = ic.local_filesystem_storage(file_path)
            repo = ic.Repository.open(storage)
            session = repo.readonly_session("main")

            datatree = xr.open_datatree(
                session.store,
                engine="zarr",
                consolidated=False,
            )
            # Temporary: inspect the actual structure
            print(f"      [DEBUG] DataTree nodes: {[node.path for node in datatree.subtree]}")
            print(f"      [DEBUG] DataTree keys: {list(datatree.keys())}")
            if "MetaData" in datatree:
                print(f"      [DEBUG] MetaData variables: {list(datatree['MetaData'].ds.data_vars)}")



            # 2. Filter observations matching the cycle time window
            if "MetaData/dateTime" in datatree and "dateTime" in datatree["MetaData"].ds:
#                dt_node = datatree["MetaData/dateTime"].ds["dateTime"]

                print(f"\n      [DEBUG] Raw MetaData/dateTime object type: {type(dt_node)}")
                print(f"      [DEBUG] Raw MetaData/dateTime dtype: {dt_node.dtype}")

                # Force concrete evaluation into a 1D NumPy array
                dt_data = datatree["MetaData"].ds["dateTime"].data
                if hasattr(dt_data, "compute"):
                    date_time = np.array(dt_data.compute(), dtype=np.int64)
                else:
                    date_time = np.array(dt_data, dtype=np.int64)

#                print(f"      [DEBUG] Evaluated date_time array type: {type(date_time)}")
#                print(f"      [DEBUG] date_time shape: {date_time.shape}, dtype: {date_time.dtype}")
                if date_time.size > 0:
                    print(f"      [DEBUG] Raw Min Epoch Sec : {date_time.min()} ({datetime.fromtimestamp(date_time.min(), tz=UTC)})")
                    print(f"      [DEBUG] Raw Max Epoch Sec : {date_time.max()} ({datetime.fromtimestamp(date_time.max(), tz=UTC)})")

                # Target window converted to integer Unix epoch seconds
                start_ts = int(self.start_window.timestamp())
                end_ts = int(self.end_window.timestamp())

#                print(f"      [DEBUG] Target Window Start Epoch : {start_ts} ({self.start_window})")
#                print(f"      [DEBUG] Target Window End Epoch   : {end_ts} ({self.end_window})")

                # Evaluate time window boolean mask
                time_mask = (date_time >= start_ts) & (date_time < end_ts)
                retained_indices = np.where(time_mask)[0]

#                print(f"      [DEBUG] time_mask sum (True count) : {np.sum(time_mask)}")
#                print(f"      [DEBUG] retained_indices length   : {len(retained_indices)}")
#                if len(retained_indices) > 0:
#                    print(f"      [DEBUG] retained_indices first 5  : {retained_indices[:5]}")
#                    print(f"      [DEBUG] retained_indices last 5   : {retained_indices[-5:]}")

                if len(retained_indices) == 0:
                    print("  [WARNING] 0 observations matched target time window.")
                    return False

                # 3. Explicitly slice each node using concrete integer indices
                filtered_nodes = {}
                for path, node in datatree.subtree_with_keys:
                    ds = node.to_dataset(inherit=False)
                    if "Location" in ds.dims:
#                        sliced = ds.isel(Location=retained_indices)
#                        print(f"      [DEBUG] Sliced node '{path}' Location dim size: {sliced.sizes.get('Location')}")
                        filtered_nodes[path] = ds.isel(Location=retained_indices)
                    else:
                        filtered_nodes[path] = ds

                # Overwrite datatree with the filtered DataTree structure
                datatree = xr.DataTree.from_dict(filtered_nodes)


            # 4. Export filtered DataTree directly to NetCDF
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

                if dt_var is not None:
                    if np.issubdtype(dt_var.dtype, np.datetime64):
                        timestamps = [
                            datetime.fromtimestamp(
                                ts.astype("datetime64[s]").astype(int), tz=UTC
                            )
                            for ts in dt_var
                        ]
                    else:
                        # int64 epoch seconds - use fromtimestamp directly, avoid timedelta overflow
                        timestamps = [
                            datetime.fromtimestamp(int(ts), tz=UTC)
                            for ts in dt_var
                            if -2**31 <= int(ts) <= 2**31 - 1 or True  # guard removed, fromtimestamp handles int64
                        ]


#                        epoch = datetime(1970, 1, 1, tzinfo=UTC)
#                        timestamps = [
#                            epoch + timedelta(seconds=int(ts)) for ts in dt_var
#                        ]

                    if len(timestamps) > 0:
                        print(
                            f"    Min Obs Time : {min(timestamps).strftime('%Y-%m-%d %H:%M:%S UTC')}"
                        )
                        print(
                            f"    Max Obs Time : {max(timestamps).strftime('%Y-%m-%d %H:%M:%S UTC')}"
                        )
                        print(f"    Total Obs    : {len(timestamps)}")
                    else:
                        print(
                            "    Total Obs    : 0 (File contains no observations inside time window)"
                        )
                else:
                    print("    MetaData/dateTime variable not found in NetCDF file.")
        except (OSError, RuntimeError, KeyError, ValueError) as e:
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
                print(f"\n=== Processing Date/Cycle: {date_str} {hr}Z [{sub_id}] ===")

                eval_out_dir = output_path.replace("{hour}", hr).replace(
                    "{date}", date_str
                )
                if not os.path.exists(eval_out_dir):
                    print(f"  [INFO] Creating output directory: {eval_out_dir}")
                    os.makedirs(eval_out_dir, exist_ok=True)

                eval_out_file = (
                    output_file_template.replace("{hour}", hr)
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

                if not success:
                    raise RuntimeError(
                        f"Conversion failed for {sub_id} at {date_str} {hr}Z"
                    )

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
