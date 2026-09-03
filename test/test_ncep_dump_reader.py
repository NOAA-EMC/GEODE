import os
import shutil
import sys
from pathlib import Path
from datetime import datetime

sys.path.append(
    os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "src")
)  # Add src/ to sys.path

from geode.configs.geode_config import geode_config
from geode.ingest.consumers import ncep_dump_reader
from geode.ingest import ingestors


def test_ncep_dump_reader():
    success = True

    reader = ncep_dump_reader.NcepDumpReader()
    reader.ingest(
        "atms", start_date=datetime(2024, 1, 1), end_date=datetime(2024, 1, 1)
    )

    # test_data_dir = os.path.join(geode_config.root_dir, "test")
    # geode_config.data_lake.base_dir = test_data_dir

    assert success, "Listener did not receive any messages"


if __name__ == "__main__":
    test_ncep_dump_reader()
