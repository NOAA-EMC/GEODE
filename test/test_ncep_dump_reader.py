import datetime
import os
import shutil
import tarfile
import tempfile
from glob import glob

import pytest
import requests

from geode.configs.geode_config import geode_config
from geode.ingest.consumers import ncep_dump_reader


@pytest.fixture(scope="module")
def download_resources():
    download_dir = os.path.join(geode_config.root_dir, "downloads")
    os.makedirs(download_dir, exist_ok=True)

    zip_url = "https://ftp.emc.ncep.noaa.gov/static_files/public/bufr-query/bufr_query-0.0.2.tgz"
    zip_path = os.path.join(download_dir, "bufr_query-0.0.2.tgz")

    if not os.path.exists(zip_path):
        response = requests.get(zip_url)
        with open(zip_path, "wb") as f:
            f.write(response.content)

        with tempfile.TemporaryDirectory() as tmp_dir:
            with tarfile.open(zip_path, "r:gz") as tar_ref:
                tar_ref.extractall(tmp_dir)

            # read the extracted bufr files into a mock dump directory
            os.makedirs(geode_config.ncep_dump.root_path, exist_ok=True)

            testdata_dir = os.path.join(tmp_dir, "remote_data", "testdata")
            if os.path.exists(testdata_dir):
                for bufr_file in glob(os.path.join(testdata_dir, "*.bufr*")):
                    for dest_loc in ["gdas.20240101", "gdas.20240102"]:
                        for dest_hr in ["00", "06", "12", "18"]:
                            dest_path = os.path.join(
                                geode_config.ncep_dump.root_path,
                                dest_loc,
                                dest_hr,
                                "atmos",
                                os.path.basename(bufr_file),
                            )
                            os.makedirs(os.path.dirname(dest_path), exist_ok=True)
                            shutil.copy(bufr_file, dest_path)
    yield


@pytest.fixture()
def cleanup(download_resources):
    shutil.rmtree(geode_config.data_lake.full_base_path, ignore_errors=True)


def test_ncep_dump_reader(cleanup):
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
