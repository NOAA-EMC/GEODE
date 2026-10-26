import datetime
import logging
import os
import shutil
import sys

import bufr

from geode.configs.geode_config import geode_config
from geode.configs.ncep_dump_config import dump_config
from geode.ingest import ingestors

logger = logging.getLogger(__name__)


class NcepDumpReader:
    def __init__(self):
        bufr.mpi.App(sys.argv)

    def _get_date_list(
        self, start_date: datetime, end_date: datetime
    ) -> list[datetime]:
        date_list = []
        current_date = start_date
        while current_date <= end_date:
            date_list.append(current_date)
            current_date += datetime.timedelta(days=1)
        return date_list

    def _stage_aux_files(self, dump_id: str) -> None:
        """Stage auxiliary files directly into the active working directory."""
        aux_files = dump_config.get_aux_files(dump_id)
        if not aux_files:
            return

        reader_dir = os.path.dirname(os.path.abspath(__file__))
        repo_root = os.path.abspath(os.path.join(reader_dir, "..", "..", "..", ".."))
        spoc_aux_dir = os.path.join(repo_root, "src", "spoc", "dump", "aux")

        if not os.path.isdir(spoc_aux_dir):
            logger.warning(f"Could not locate SPOC aux directory: {spoc_aux_dir}")
            print(
                f"[AUX WARN] Could not locate SPOC aux directory: {spoc_aux_dir}",
                flush=True,
            )
            return

        cwd = os.getcwd()
        for aux_file in aux_files:
            src = os.path.join(spoc_aux_dir, aux_file)
            dest = os.path.join(cwd, os.path.basename(src))

            if not os.path.exists(dest):
                if os.path.exists(src):
                    shutil.copy2(src, dest)
                    logger.info(f"Staged auxiliary file: {src} -> {dest}")
                    print(
                        f"[AUX WARN] Could not locate SPOC aux directory: {spoc_aux_dir}",
                        flush=True,
                    )
                else:
                    logger.warning(
                        f"Auxiliary file missing in source dir ({spoc_aux_dir}): {src}"
                    )
                    print(
                        f"[AUX WARN] Could not locate SPOC aux directory: {spoc_aux_dir}",
                        flush=True,
                    )
            else:
                logger.info(f"Auxiliary file already present in cwd: {dest}")

    def ingest(self, dump_id: str, start_date: datetime, end_date: datetime) -> None:
        # Stage auxiliary files prior to reading/ingesting
        self._stage_aux_files(dump_id)

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
