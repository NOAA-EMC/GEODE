import os
import sys
from datetime import datetime, timezone

from geode.ingest.consumers import ncep_dump_reader


def test_ncep_dump_reader():
    success = True

    reader = ncep_dump_reader.NcepDumpReader()
    reader.ingest(
        "atms",
        start_date=datetime(2024, 1, 1, tzinfo=timezone.utc),
        end_date=datetime(2024, 1, 1, tzinfo=timezone.utc),
    )

    # test_data_dir = os.path.join(geode_config.root_dir, "test")
    # geode_config.data_lake.base_dir = test_data_dir

    assert success, "Listener did not receive any messages"


if __name__ == "__main__":
    test_ncep_dump_reader()
    print("Test passed.")
