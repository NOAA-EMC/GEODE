import os
import argparse
from datetime import datetime, timedelta
import sys

import bufr

from geode.configs.geode_config import geode_config
from geode.ingest import ingestors


class NcepDumpReader:
    def __init__(self):
        bufr.mpi.App(sys.argv)

    def _get_date_list(self, start_date: datetime, end_date: datetime) -> list[datetime]:
        date_list = []
        current_date = start_date
        while current_date <= end_date:
            date_list.append(current_date)
            current_date += timedelta(days=1)
        return date_list

    def ingest(self, dump_id: str, start_date: datetime, end_date: datetime) -> None:
        date_list = self._get_date_list(start_date, end_date)
        file_paths = []
        for day in date_list:
            file_paths.extend(geode_config.ncep_dump.get_file_paths(dump_id, day))

        # Process the downloaded file with the appropriate ingestor if available
        ingestor_class = ingestors.make(f"ncep_dump/{dump_id}")

        if ingestor_class:
            for file_path in file_paths:
                ingestor = ingestor_class()
                ingestor.process(file_path)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Read NCEP dump file")
    parser.add_argument("id", type=str, help="ID for the data type")
    parser.add_argument("start_date", type=str, help="Start date in YYYY-MM-DD format")
    parser.add_argument("end_date", type=str, help="End date in YYYY-MM-DD format")
    args = parser.parse_args()

    start_date = datetime.strptime(args.start_date, "%Y-%m-%d")
    end_date = datetime.strptime(args.end_date, "%Y-%m-%d")
    
    NcepDumpReader().ingest(args.id, start_date, end_date)
