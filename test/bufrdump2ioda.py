import sys
import os
import glob
import argparse
from datetime import datetime, timedelta, timezone
from pathlib import Path
import yaml
import numpy as np
import netCDF4 as nc
import bufr.bufr_python as pybufr

# Define UTC timezone for Python versions < 3.11 compatibility
UTC = timezone.utc

class BufrToIODAnetCDF:
    def __init__(
        self,
        obs_file: str,
        mapping_file: str,
        output_file: str,
        table_path: str = "",
    ):
        self.obs_file = obs_file
        self.mapping_file = mapping_file
        self.output_file = output_file
        self.table_path = table_path

    def convert(self, num_messages: int = 0):
        print(f"  --> Processing BUFR file: {self.obs_file}")

        if not os.path.exists(self.obs_file):
            print(f"  [WARNING] Input file does not exist: {self.obs_file}. Skipping.")
            return False

        # 1. Parse BUFR data
        print("      Parsing BUFR...")
        parser = pybufr.Parser(self.obs_file, self.mapping_file, self.table_path)
        data = parser.parse(num_messages)

        # 2. Instantiate Encoder
        print("      Instantiating Encoder...")
        encoder = pybufr.encoders.netcdf.Encoder(self.mapping_file)

        # 3. Encode data directly to output file
        print(f"      Encoding Data to: {self.output_file}")
        encoder.encode(data, self.output_file)
        return True


def get_assimilation_window(cycle_date_str: str, cycle_hour: int) -> tuple[datetime, datetime]:
    """
    Computes [start_time, end_time) UTC for a given cycle hour:
      00z: 21z (prev day)  to 03z (current day)
      06z: 03z (current day) to 09z (current day)
      12z: 09z (current day) to 15z (current day)
      18z: 15z (current day) to 03z (next day)
    """
    base_dt = datetime.strptime(cycle_date_str, "%Y-%m-%d").replace(tzinfo=UTC)

    if cycle_hour == 0:
        start_time = base_dt - timedelta(hours=3)        # 21z previous day
        end_time = base_dt + timedelta(hours=3)          # 03z current day
    elif cycle_hour == 6:
        start_time = base_dt + timedelta(hours=3)        # 03z current day
        end_time = base_dt + timedelta(hours=9)          # 09z current day
    elif cycle_hour == 12:
        start_time = base_dt + timedelta(hours=9)        # 09z current day
        end_time = base_dt + timedelta(hours=15)         # 15z current day
    elif cycle_hour == 18:
        start_time = base_dt + timedelta(hours=15)       # 15z current day
        end_time = base_dt + timedelta(days=1, hours=3)  # 03z next day
    else:
        raise ValueError(f"Invalid cycle hour: {cycle_hour}. Must be 0, 6, 12, or 18.")

    return start_time, end_time


def slice_netcdf_time_window(output_pattern: str, start_dt: datetime, end_dt: datetime) -> None:
    """
    Slices generated NetCDF file(s) along the Location dimension to retain
    ONLY observations that fall within [start_dt, end_dt).
    """
    glob_pattern = output_pattern.replace("{splits/satId}", "*")
    matching_files = glob.glob(glob_pattern)

    start_epoch = int(start_dt.timestamp())
    end_epoch = int(end_dt.timestamp())

    for nc_file in matching_files:
        path = Path(nc_file)
        if not path.is_file():
            continue

        try:
            with nc.Dataset(nc_file, "r") as src:
                if "MetaData" not in src.groups or "dateTime" not in src.groups["MetaData"].variables:
                    print(f"  Warning: MetaData/dateTime not found in {path.name}. Skipping slicing.")
                    continue

                dt_var = src.groups["MetaData"]["dateTime"][:]

                # Find indices inside the time window
                valid_indices = np.where((dt_var >= start_epoch) & (dt_var < end_epoch))[0]

                if len(valid_indices) == len(dt_var):
                    print(f"  {path.name}: All {len(dt_var)} observations already within time window.")
                    continue

                print(f"  Filtering {path.name}: Retaining {len(valid_indices)} / {len(dt_var)} observations...")

                tmp_nc = nc_file + ".tmp"
                with nc.Dataset(tmp_nc, "w", format=src.file_format) as dst:
                    # 1. Copy root global attributes
                    dst.setncatts(src.__dict__)
                    # 2. Copy and update dimensions
                    for dim_name, dimension in src.dimensions.items():
                        if dim_name == "Location":
                            dst.createDimension(dim_name, len(valid_indices))
                        else:
                            dst.createDimension(dim_name, len(dimension) if not dimension.isunlimited() else None)

                    # 3. Recursively copy and slice variables and subgroups
                    def copy_and_slice_group(src_grp, dst_grp):
                        dst_grp.setncatts(src_grp.__dict__)

                        for var_name, variable in src_grp.variables.items():
                            fill_val = getattr(variable, "_FillValue", None)
                            var_kwargs = {"fill_value": fill_val} if fill_val is not None else {}

                            dst_var = dst_grp.createVariable(
                                var_name, variable.datatype, variable.dimensions, **var_kwargs
                            )
                            # Copy variable attributes
                            dst_var.setncatts({k: v for k, v in variable.__dict__.items() if k != "_FillValue"})

                            # Slice data if 'Location' is the first dimension
                            var_data = variable[:]
                            if len(variable.dimensions) > 0 and variable.dimensions[0] == "Location":
                                if len(valid_indices) > 0:
                                    dst_var[:] = var_data[valid_indices, ...]
                                else:
                                    # Handle empty slice case gracefully
                                    empty_shape = (0,) + var_data.shape[1:]
                                    dst_var[:] = np.empty(empty_shape, dtype=variable.datatype)
                            else:
                                dst_var[:] = var_data

                        for grp_name, grp in src_grp.groups.items():
                            sub_dst = dst_grp.createGroup(grp_name)
                            copy_and_slice_group(grp, sub_dst)

                    copy_and_slice_group(src, dst)

                # Atomically replace original NetCDF file with the sliced file
                Path(tmp_nc).replace(path)

        except Exception as e:
            print(f"  Error slicing {nc_file}: {e}", file=sys.stderr)


def print_netcdf_time_summary(output_pattern: str) -> None:
    """Inspects generated IODA NetCDF file(s) and prints observation time bounds."""
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
                if "MetaData" in ds.groups and "dateTime" in ds.groups["MetaData"].variables:
                    dt_var = ds.groups["MetaData"]["dateTime"][:]
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


def run_batch_conversion(data_type_id: str, start_date_str: str, end_date_str: str, config_path: str = "config.yaml"):
    # Load YAML Configuration
    with open(config_path, "r") as f:
        config = yaml.safe_load(f)

    hours = config.get("hours", ["00", "06", "12", "18"])
    data_types = config.get("data_types", [])

    dt_config = next((item for item in data_types if item["id"] == data_type_id), None)
    if not dt_config:
        raise ValueError(f"Data type '{data_type_id}' not found in configuration file '{config_path}'.")

    # Parse parameters from config
    bufr_path = dt_config.get("bufr_path", dt_config.get("path_bufr", ""))
    bufr_file = dt_config.get("bufr_file", "")
    output_path = dt_config.get("output_path", dt_config.get("path_output", ""))
    output_file_template = dt_config.get("output_file", dt_config.get("output_files", ""))
    mapping_file = dt_config.get("mapping_file", dt_config.get("path_mapping", ""))

    # Ensure leading slash for absolute pathing
    if bufr_path and not bufr_path.startswith("/"):
        bufr_path = "/" + bufr_path
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

            # 1. Evaluate output directory and create it BEFORE combining paths
            eval_out_dir = output_path.replace("{hour}", hr).replace("{date}", date_str)
            if not os.path.exists(eval_out_dir):
                print(f"  [INFO] Creating output directory: {eval_out_dir}")
                os.makedirs(eval_out_dir, exist_ok=True)

            # 2. Evaluate filenames
            eval_bufr_dir = bufr_path.replace("{hour}", hr).replace("{date}", date_str)
            eval_bufr_file = bufr_file.replace("{hour}", hr).replace("{date}", date_str)
            obs_file = os.path.join(eval_bufr_dir, eval_bufr_file)

            eval_out_file = output_file_template.replace("{hour}", hr).replace("{date}", date_str)
            output_file = os.path.join(eval_out_dir, eval_out_file)

            # 3. Convert BUFR to NetCDF
            converter = BufrToIODAnetCDF(
                obs_file=obs_file,
                mapping_file=mapping_file,
                output_file=output_file,
            )
            success = converter.convert()

            # 4. Slice generated NetCDF to cycle assimilation window
            if success:
                start_window, end_window = get_assimilation_window(formatted_date, cycle_hour)
                print(f"  [TIME WINDOW] Slicing observations between {start_window} and {end_window}")
                slice_netcdf_time_window(output_file, start_window, end_window)
                print_netcdf_time_summary(output_file)

        current_date += timedelta(days=1)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Convert BUFR files to IODA NetCDF format over a date range.")
    parser.add_argument("data_type", type=str, help="Data type ID defined in config (e.g., iasi, atms)")
    parser.add_argument("start_date", type=str, help="Start date in YYYY-MM-DD format")
    parser.add_argument("end_date", type=str, help="End date in YYYY-MM-DD format")
    parser.add_argument("--config", type=str, default="config.yaml", help="Path to YAML configuration file")

    args = parser.parse_args()

    print(f"Starting conversion for data_type={args.data_type} from {args.start_date} to {args.end_date}")
    run_batch_conversion(args.data_type, args.start_date, args.end_date, args.config)
    print("\nBatch conversion process complete!")
