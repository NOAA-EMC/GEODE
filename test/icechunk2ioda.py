import sys
import os
import glob
import argparse
from datetime import datetime, timedelta, timezone
from pathlib import Path
import yaml
import numpy as np
import netCDF4 as nc
import xarray as xr
import zarr
import icechunk

'''
usage
python icechunk2ioda.py cris_npp_icechunk 2026-09-13 2026-09-19

As of Set 28, 2026 available data types are
iasi_metop-a_icechunk, iasi_metop-b_icechunk, iasi_metop-c_icechunk
cris_npp_icechunk, cris_n20_icechunk, cris_n21_icechunk
atms_npp_icechunk, atms_n20_icechunk, atms_n21_icechunk
radiosonde
'''

# Define UTC timezone for Python versions < 3.11 compatibility
UTC = timezone.utc


class IcechunkToIODAnetCDF:
    def __init__(
        self,
        repo_path: str,
        output_file: str,
        branch: str = "main",
        snapshot_id: str = None,
        tag: str = None,
        start_window: datetime = None,
        end_window: datetime = None,
        debug: bool = False,
    ):
        self.repo_path = repo_path
        self.output_file = output_file
        self.branch = branch
        self.snapshot_id = snapshot_id
        self.tag = tag
        self.start_window = start_window
        self.end_window = end_window
        self.debug = debug

    def _log_debug(self, msg: str):
        if self.debug:
            print(f"  [DEBUG] {msg}")

    def load_dataset_recursively(self, store) -> tuple[xr.Dataset, zarr.Group]:
        """
        Recursively opens Zarr v3 groups and merges them into a single Xarray dataset,
        preserving IODA variable paths (e.g., 'MetaData/dateTime', 'ObsValue/spectralRadiance').
        """
        zgroup = zarr.open_group(store, mode="r")

        subgroups = [name for name, obj in zgroup.members() if isinstance(obj, zarr.Group)]
        arrays = [name for name, obj in zgroup.members() if isinstance(obj, zarr.Array)]

        self._log_debug(f"Root Zarr Groups found: {subgroups}")
        self._log_debug(f"Root Zarr Arrays found: {arrays}")

        group_dict = {}

        def walk_zarr_group(group: zarr.Group, current_path: str = ""):
            for name, child in group.members():
                full_path = f"{current_path}/{name}".lstrip("/")

                if isinstance(child, zarr.Group):
                    walk_zarr_group(child, full_path)
                elif isinstance(child, zarr.Array):
                    parent_group = os.path.dirname(full_path)
                    var_name = os.path.basename(full_path)

                    try:
                        ds_sub = xr.open_zarr(
                            store,
                            group=parent_group if parent_group else None,
                            zarr_format=3,
                        )
                        if var_name in ds_sub:
                            group_dict[full_path] = ds_sub[var_name]
                    except Exception as e:
                        self._log_debug(f"Failed to load variable '{full_path}' into Xarray: {e}")

        walk_zarr_group(zgroup)

        if not group_dict:
            self._log_debug("No nested arrays found during traversal, opening root group...")
            ds = xr.open_zarr(store, zarr_format=3)
        else:
            ds = xr.Dataset(group_dict)

        return ds, zgroup

    def find_datetime_variable(self, ds: xr.Dataset):
        """Locates the dateTime variable in the Xarray dataset."""
        candidates = [
            "MetaData/dateTime",
            "MetaData/datetime",
            "dateTime",
            "datetime",
            "time",
        ]

        for key in candidates:
            if key in ds:
                self._log_debug(f"Found dateTime variable in dataset: '{key}'")
                return ds[key]

        for key in ds.variables:
            if key.endswith("dateTime") or key.endswith("datetime"):
                self._log_debug(f"Found dateTime variable in dataset: '{key}'")
                return ds[key]

        return None

    def write_dataset_to_ioda_nc(self, ds: xr.Dataset, output_file: str):
        """
        Writes a flat Xarray dataset with group-path keys (e.g. 'MetaData/dateTime')
        into a proper IODA NetCDF4 file containing actual NetCDF groups.
        """
        out_path = Path(output_file)
        out_path.parent.mkdir(parents=True, exist_ok=True)

        with nc.Dataset(output_file, "w", format="NETCDF4") as dst:
            # 1. Use ds.sizes to avoid Xarray FutureWarning
            for dim_name, dim_size in ds.sizes.items():
                dst.createDimension(dim_name, dim_size)

            # 2. Iterate and place variables into NetCDF groups
            for key, var in ds.variables.items():
                if "/" in key:
                    group_name, var_name = key.split("/", 1)
                    grp = dst.groups.get(group_name) or dst.createGroup(group_name)
                else:
                    grp = dst
                    var_name = key

                fill_val = var.encoding.get("_FillValue", None)
                kwargs = {"fill_value": fill_val} if fill_val is not None else {}

                data = var.values
                if np.issubdtype(data.dtype, np.datetime64):
                    data = data.astype("datetime64[s]").astype(np.int64)
                    dtype = np.int64
                else:
                    # Enforce native byte order to eliminate netCDF4 endian warnings
                    dtype = data.dtype.newbyteorder("=")

                nc_var = grp.createVariable(
                    var_name, dtype, var.dims, **kwargs
                )

                for attr_name, attr_val in var.attrs.items():
                    if attr_name != "_FillValue":
                        nc_var.setncattr(attr_name, attr_val)

                nc_var[:] = data

    def convert(self) -> bool:
        print(f"  --> Opening Icechunk repo: {self.repo_path}")

        if not os.path.exists(self.repo_path):
            print(f"  [WARNING] Repository path does not exist: {self.repo_path}. Skipping.")
            return False

        try:
            # 1. Open Repository
            repo = icechunk.Repository.open(
                storage=icechunk.local_filesystem_storage(self.repo_path)
            )

            # 2. Open Read-Only Session
            if self.snapshot_id:
                print(f"      Reading Session Snapshot: {self.snapshot_id}")
                session = repo.readonly_session(snapshot_id=self.snapshot_id)
            elif self.tag:
                print(f"      Reading Session Tag: {self.tag}")
                session = repo.readonly_session(tag=self.tag)
            else:
                print(f"      Reading Session Branch: {self.branch}")
                session = repo.readonly_session(branch=self.branch)

            # 3. Load full hierarchy into Xarray
            print("      Loading Xarray dataset and Zarr hierarchy from Icechunk store...")
            ds, zgroup = self.load_dataset_recursively(session.store)

            self._log_debug(f"Loaded Xarray Dataset Summary:\n{ds}")

            # 4. Filter by Time Window
            if self.start_window and self.end_window:
                dt_var = self.find_datetime_variable(ds)

                if dt_var is not None:
                    # Parse Target Dates based on dtype
                    if np.issubdtype(dt_var.dtype, np.datetime64):
                        start_target = np.datetime64(self.start_window.replace(tzinfo=None))
                        end_target = np.datetime64(self.end_window.replace(tzinfo=None))
                    else:
                        start_target = int(self.start_window.timestamp())
                        end_target = int(self.end_window.timestamp())

                    # Force immediate loading of dateTime array values into NumPy
                    dt_values = np.asarray(dt_var.values)

                    if len(dt_values) > 0:
                        min_dt = dt_values.min()
                        max_dt = dt_values.max()
                        self._log_debug(f"Icechunk Store Min Date: {min_dt} | Max Date: {max_dt}")

                    # Compute explicit 1D boolean array
                    mask = np.logical_and(dt_values >= start_target, dt_values < end_target)
                    retained_indices = np.where(mask)[0]
                    retained_count = len(retained_indices)
                    total_count = len(dt_values)

                    print(f"      Filtering: Retaining {retained_count} / {total_count} observations...")

                    # Explicitly slice along Location dimension using index positions
                    if "Location" in ds.dims:
                        ds = ds.isel(Location=retained_indices)
                else:
                    print("  [WARNING] dateTime variable not found in dataset. Skipping time window filtering.")

            # 5. Output directory preparation and NetCDF export
            print(f"      Encoding Data to IODA NetCDF: {self.output_file}")
            self.write_dataset_to_ioda_nc(ds, self.output_file)
            return True

        except Exception as e:
            print(f"  [ERROR] Failed during Icechunk conversion: {e}", file=sys.stderr)
            if self.debug:
                import traceback
                traceback.print_exc()
            return False


def get_assimilation_window(cycle_date_str: str, cycle_hour: int) -> tuple[datetime, datetime]:
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
#       end_time = base_dt + timedelta(days=1, hours=3)
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
                if "MetaData" in ds.groups and "dateTime" in ds.groups["MetaData"].variables:
                    dt_var = ds.groups["MetaData"]["dateTime"][:]
                elif "dateTime" in ds.variables:
                    dt_var = ds.variables["dateTime"][:]

                if dt_var is not None:
                    if np.issubdtype(dt_var.dtype, np.datetime64):
                        timestamps = [datetime.fromtimestamp(ts.astype('datetime64[s]').astype(int), tz=UTC) for ts in dt_var]
                    else:
                        epoch = datetime(1970, 1, 1, tzinfo=UTC)
                        timestamps = [epoch + timedelta(seconds=int(ts)) for ts in dt_var]

                    if len(timestamps) > 0:
                        print(f"    Min Obs Time : {min(timestamps).strftime('%Y-%m-%d %H:%M:%S UTC')}")
                        print(f"    Max Obs Time : {max(timestamps).strftime('%Y-%m-%d %H:%M:%S UTC')}")
                        print(f"    Total Obs    : {len(timestamps)}")
                    else:
                        print("    Total Obs    : 0 (File contains no observations inside time window)")
                else:
                    print("    MetaData/dateTime variable not found in NetCDF file.")
        except Exception as e:
            print(f"    Could not read NetCDF file: {e}")


def run_batch_conversion(
    data_type_id: str,
    start_date_str: str,
    end_date_str: str,
    config_path: str = "config.yaml",
    debug: bool = False,
):
    with open(config_path, "r") as f:
        config = yaml.safe_load(f)

    hours = config.get("hours", ["00", "06", "12", "18"])
    data_types = config.get("data_types", [])

    dt_config = next((item for item in data_types if item["id"] == data_type_id), None)
    if not dt_config:
        raise ValueError(f"Data type '{data_type_id}' not found in configuration file '{config_path}'.")

    icechunk_path = dt_config.get("icechunk_path", dt_config.get("path_icechunk", ""))
    icechunk_repo = dt_config.get("icechunk_repo", dt_config.get("repo_name", ""))
    output_path = dt_config.get("output_path", dt_config.get("path_output", ""))
    output_file_template = dt_config.get("output_file", dt_config.get("output_files", ""))

    branch = dt_config.get("branch", "main")
    snapshot_id = dt_config.get("snapshot_id", None)
    tag = dt_config.get("tag", None)

    if icechunk_path and not icechunk_path.startswith("/"):
        icechunk_path = "/" + icechunk_path
    if output_path and not output_path.startswith("/"):
        output_path = "/" + output_path

    start_date = datetime.strptime(start_date_str, "%Y-%m-%d")
    end_date = datetime.strptime(end_date_str, "%Y-%m-%d")

    current_date = start_date
    while current_date <= end_date:
        date_str = current_date.strftime("%Y%m%d")
        formatted_date = current_date.strftime("%Y-%m-%d")

        for hr in hours:
            cycle_hour = int(hr)
            print(f"\n=== Processing Date/Cycle: {date_str} {hr}Z ===")

            eval_out_dir = output_path.replace("{hour}", hr).replace("{date}", date_str)
            if not os.path.exists(eval_out_dir):
                print(f"  [INFO] Creating output directory: {eval_out_dir}")
                os.makedirs(eval_out_dir, exist_ok=True)

            eval_icechunk_dir = icechunk_path
            if "{hour}" in eval_icechunk_dir:
                eval_icechunk_dir = eval_icechunk_dir.replace("{hour}", hr)
            if "{date}" in eval_icechunk_dir:
                eval_icechunk_dir = eval_icechunk_dir.replace("{date}", date_str)

            eval_icechunk_repo = icechunk_repo
            if "{hour}" in eval_icechunk_repo:
                eval_icechunk_repo = eval_icechunk_repo.replace("{hour}", hr)
            if "{date}" in eval_icechunk_repo:
                eval_icechunk_repo = eval_icechunk_repo.replace("{date}", date_str)

            repo_full_path = os.path.join(eval_icechunk_dir, eval_icechunk_repo)

            # Format output filename directly matching NOAA GDAS convention: gdas.t{hr}z.prepbufr_adpupa.nc
            if not output_file_template:
                eval_out_file = f"gdas.t{hr}z.prepbufr_adpupa.nc"
            else:
                eval_out_file = output_file_template.replace("{hour}", hr).replace("{date}", date_str)

            output_file = os.path.join(eval_out_dir, eval_out_file)

            start_window, end_window = get_assimilation_window(formatted_date, cycle_hour)
            print(f"  [TIME WINDOW] Target range: {start_window} to {end_window}")

            converter = IcechunkToIODAnetCDF(
                repo_path=repo_full_path,
                output_file=output_file,
                branch=branch,
                snapshot_id=snapshot_id,
                tag=tag,
                start_window=start_window,
                end_window=end_window,
                debug=debug,
            )
            success = converter.convert()

            if success:
                print_netcdf_time_summary(output_file, debug=debug)

        current_date += timedelta(days=1)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Convert Icechunk repositories to IODA NetCDF format over a date range."
    )
    parser.add_argument("data_type", type=str, help="Data type ID defined in config (e.g., cris_n20_icechunk)")
    parser.add_argument("start_date", type=str, help="Start date in YYYY-MM-DD format")
    parser.add_argument("end_date", type=str, help="End date in YYYY-MM-DD format")
    parser.add_argument("--config", type=str, default="config.yaml", help="Path to YAML configuration file")
    parser.add_argument("--debug", action="store_true", help="Enable verbose debug logging and stack traces")

    args = parser.parse_args()

    print(f"Starting conversion for data_type={args.data_type} from {args.start_date} to {args.end_date}")
    if args.debug:
        print("[DEBUG] Debug logging enabled.")

    run_batch_conversion(
        args.data_type, args.start_date, args.end_date, config_path=args.config, debug=args.debug
    )
    print("\nBatch conversion process complete!")
