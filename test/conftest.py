import datetime
import os
import shutil
import tarfile
import tempfile
from glob import glob
from pathlib import Path

import pytest
import requests

from geode.configs.geode_config import geode_config

REQUEST_TIMEOUT_SECONDS = 30


def _safe_extract_tar(tar_ref: tarfile.TarFile, destination: str) -> None:
    """Safely extract a tar archive into a destination directory.

    Parameters
    ----------
    tar_ref : tarfile.TarFile
        Open tar archive handle to extract.
    destination : str
        Directory that receives extracted archive members.

    Returns
    -------
    None
        This helper extracts the archive in place.

    Raises
    ------
    tarfile.TarError
        Raised when an archive member would escape the target directory or is
        an unsupported link or device entry.
    """
    destination_path = Path(destination).resolve()

    for member in tar_ref.getmembers():
        member_path = (destination_path / member.name).resolve()
        if os.path.commonpath((destination_path, member_path)) != str(destination_path):
            raise tarfile.TarError(
                f"FATAL ERROR: Refusing to extract path outside {destination_path}"
            )
        if member.issym() or member.islnk() or member.isdev():
            raise tarfile.TarError(
                f"FATAL ERROR: Refusing to extract unsupported tar member {member.name}"
            )
        tar_ref.extract(member, destination_path)


@pytest.fixture(scope="session")
def use_dump():
    download_dir = os.path.join(geode_config.root_dir, "downloads")
    os.makedirs(download_dir, exist_ok=True)

    zip_url = "https://ftp.emc.ncep.noaa.gov/static_files/public/bufr-query/bufr_query-0.0.2.tgz"
    zip_path = os.path.join(download_dir, "bufr_query-0.0.2.tgz")

    if not os.path.exists(zip_path):
        response = requests.get(zip_url, timeout=REQUEST_TIMEOUT_SECONDS)
        response.raise_for_status()
        with open(zip_path, "wb") as f:
            f.write(response.content)

        with tempfile.TemporaryDirectory() as tmp_dir:
            with tarfile.open(zip_path, "r:gz") as tar_ref:
                _safe_extract_tar(tar_ref, tmp_dir)

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
def use_empty_data_lake():
    os.makedirs(geode_config.data_lake.full_base_path, exist_ok=True)

    yield

    shutil.rmtree(geode_config.data_lake.full_base_path, ignore_errors=True)


@pytest.fixture()
def use_data_lake(use_dump):
    from geode.ingest.consumers import ncep_dump_reader

    os.makedirs(geode_config.data_lake.full_base_path, exist_ok=True)

    reader = ncep_dump_reader.NcepDumpReader()
    reader.ingest(
        "atms",
        start_date=datetime.datetime(2024, 1, 1, tzinfo=datetime.UTC),
        end_date=datetime.datetime(2024, 1, 2, tzinfo=datetime.UTC),
    )

    yield

    shutil.rmtree(geode_config.data_lake.full_base_path, ignore_errors=True)
