
import os
import shutil
import sys
import tarfile
import tempfile

from datetime import datetime, timezone
from glob import glob

import pytest
import requests

from geode.configs.geode_config import geode_config
from geode.configs import ncep_dump_config
from geode.ingest.consumers import ncep_dump_reader


DataDir = os.path.join(os.path.dirname(__file__), "data")
DownloadDir = DataDir
DumpDir = os.path.join(DataDir, "dump")
LakeDir = os.path.join(DataDir, "lake")

ConfigsDir = os.path.realpath(os.path.join(os.path.dirname(__file__), "configs"))



@pytest.fixture(scope="module")
def download_resources():
    os.makedirs(DataDir, exist_ok=True)
    os.makedirs(DownloadDir, exist_ok=True)

    zip_url = "https://ftp.emc.ncep.noaa.gov/static_files/public/bufr-query/bufr_query-0.0.2.tgz"
    zip_path = os.path.join(DownloadDir, "bufr_query-0.0.2.tgz")

    if not os.path.exists(zip_path):
        response = requests.get(zip_url)
        with open(zip_path, "wb") as f:
            f.write(response.content)

        with tempfile.TemporaryDirectory() as tmp_dir:
            with tarfile.open(zip_path, "r:gz") as tar_ref:
                tar_ref.extractall(tmp_dir)

            # read the extracted bufr files into a mock dump directory
            os.makedirs(DumpDir, exist_ok=True)

            testdata_dir = os.path.join(tmp_dir, "remote_data", "testdata")
            if os.path.exists(testdata_dir):
                for bufr_file in glob(os.path.join(testdata_dir, "*.bufr*")):
                    for dest_loc in ["gdas.20240101", "gdas.20240102"]:
                        for dest_hr in ["00", "06", "12", "18"]:
                            dest_path = os.path.join(
                                DumpDir, dest_loc, dest_hr, "atmos", os.path.basename(bufr_file)
                            )
                            os.makedirs(os.path.dirname(dest_path), exist_ok=True)
                            shutil.copy(bufr_file, dest_path)


@pytest.fixture(scope="module")
def set_configs(download_resources):
    geode_config.data_lake.base_dir = LakeDir
    geode_config.ncep_dump.root_path = DumpDir
    ncep_dump_config.dump_config = \
        ncep_dump_config.DumpConfig(os.path.join(ConfigsDir, "ncep_dump.yaml"))


def test_ncep_dump_reader(set_configs):

    success = True

    print ("Starting test_ncep_dump_reader")

    reader = ncep_dump_reader.NcepDumpReader()
    reader.ingest(
        "mhs",
        start_date=datetime(2024, 1, 1, tzinfo=timezone.utc),
        end_date=datetime(2024, 1, 1, tzinfo=timezone.utc),
    )

    # test_data_dir = os.path.join(geode_config.root_dir, "test")
    # geode_config.data_lake.base_dir = test_data_dir

    assert success, "Listener did not receive any messages"


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-v"]))
