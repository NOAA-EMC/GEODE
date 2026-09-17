import sys
import os
import argparse
from datetime import datetime, timedelta
import yaml
import bufr.bufr_python as pybufr


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
            return

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
    bufr_path = dt_config.get("bufr_path", "")
    bufr_file = dt_config.get("bufr_file", "")
    output_path = dt_config.get("output_path", "")
    output_file_template = dt_config.get("output_file", "")
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

        for hr in hours:
            print(f"\n=== Processing Date/Cycle: {date_str} {hr}Z ===")

            # 1. Evaluate output directory and make it BEFORE combining with filename
            eval_out_dir = output_path.replace("{hour}", hr).replace("{date}", date_str)
            if not os.path.exists(eval_out_dir):
                print(f"  [INFO] Creating output directory: {eval_out_dir}")
                os.makedirs(eval_out_dir, exist_ok=True)

            # 2. Evaluate filenames
            eval_bufr_dir = bufr_path.replace("{hour}", hr).replace("{date}", date_str)
            eval_bufr_file = bufr_file.replace("{hour}", hr).replace("{date}", date_str)
            obs_file = os.path.join(eval_bufr_dir, eval_bufr_file)

            eval_out_file = output_file_template.replace("{hour}", hr).replace("{date}", date_str)
            
            # 3. Combine directory + filename
            output_file = os.path.join(eval_out_dir, eval_out_file)

            converter = BufrToIODAnetCDF(
                obs_file=obs_file,
                mapping_file=mapping_file,
                output_file=output_file,
            )
            converter.convert()

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
