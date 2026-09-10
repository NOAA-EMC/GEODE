import datetime
import os

import pytest

from geode.configs.geode_config import geode_config
from geode.ingest.consumers import ncep_dump_reader


def test_ncep_dump_reader(use_dump, use_empty_data_lake):
    success = False

    print("Starting test_ncep_dump_reader")

    reader = ncep_dump_reader.NcepDumpReader()
    reader.ingest(
        "atms",
        start_date=datetime.datetime(2024, 1, 1, tzinfo=datetime.UTC),
        end_date=datetime.datetime(2024, 1, 1, tzinfo=datetime.UTC),
    )

    result_path = os.path.join(
        geode_config.data_lake.full_base_path, "atms_n20.icechunk"
    )

    if os.path.exists(result_path):
        success = True

    assert success, "Listener did not receive any messages"


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-v"]))
