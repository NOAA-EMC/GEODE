import os
import pytest
import shutil
import tarfile
import tempfile

from glob import glob
from pathlib import Path

import numpy as np
import requests
import xarray as xr

from geode.data.keys import IsSortedFlag
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
def use_empty_data_lake(tmp_path, monkeypatch):
    monkeypatch.setattr(geode_config.data_lake, "root_dir", str(tmp_path))
    os.makedirs(geode_config.data_lake.full_base_path, exist_ok=True)

    yield

    shutil.rmtree(geode_config.data_lake.full_base_path, ignore_errors=True)


@pytest.fixture()
def use_data_lake(use_empty_data_lake):
    from geode.data.manager import data_manager

    slice_times = np.arange(
        np.datetime64("2021-07-30T00", "m"),
        np.datetime64("2021-08-01T00", "m"),
        np.timedelta64(1, "m"),
    )
    times, latitudes = np.meshgrid(
        slice_times,
        np.arange(-20.0, 21.0, 1.0),
        indexing="ij",
    )
    longitudes = np.broadcast_to(
        np.linspace(-180.0, 180.0, slice_times.size, endpoint=False)[:, None],
        times.shape,
    )
    stripe = xr.DataTree.from_dict(
        {
            "/": xr.Dataset(
                coords={"Location": np.arange(times.size)},
                attrs={
                    IsSortedFlag: True,
                    "history": (
                        "Created deterministic equatorial test stripe sweeping "
                        "eastward at one longitude slice per minute, with "
                        "temperature increasing by 0.1 K per degree longitude."
                    ),
                },
            ),
            "/MetaData": xr.Dataset(
                coords={
                    "dateTime": ("Location", times.ravel().astype("datetime64[s]")),
                    "latitude": (
                        "Location",
                        latitudes.ravel(),
                        {"units": "degrees_north"},
                    ),
                    "longitude": (
                        "Location",
                        longitudes.ravel(),
                        {"units": "degrees_east"},
                    ),
                }
            ),
            "/ObsValue": xr.Dataset(
                {
                    "temperature": (
                        "Location",
                        280.0 + 0.1 * latitudes.ravel() + 0.1 * longitudes.ravel(),
                        {"units": "K"},
                    )
                }
            ),
        }
    )
    data_manager.put("stripe", stripe)

    times, latitudes, longitudes = np.meshgrid(
        np.array(
            [
                "2021-07-30T00:00:00",
                "2021-07-31T00:00:00",
                "2021-07-31T22:44:00",
                "2021-07-31T22:44:30",
            ],
            dtype="datetime64[s]",
        ),
        np.arange(-90.0, 91.0, 2.0),
        np.arange(-180.0, 180.0, 2.0),
        indexing="ij",
    )
    channels = np.arange(1, 5)
    temperature = 280.0 + 0.1 * latitudes.ravel() + 0.1 * longitudes.ravel()
    globe = xr.DataTree.from_dict(
        {
            "/": xr.Dataset(
                coords={"Location": np.arange(times.size), "Channel": channels},
                attrs={
                    "history": (
                        "Created deterministic global test grid at 2-degree "
                        "spacing, with four time slices and four channels."
                    )
                },
            ),
            "/MetaData": xr.Dataset(
                {
                    "sensorChannelNumber": (
                        ("Location", "Channel"),
                        np.broadcast_to(channels, (times.size, channels.size)),
                    )
                },
                coords={
                    "dateTime": ("Location", times.ravel()),
                    "latitude": (
                        "Location",
                        latitudes.ravel(),
                        {"units": "degrees_north"},
                    ),
                    "longitude": (
                        "Location",
                        longitudes.ravel(),
                        {"units": "degrees_east"},
                    ),
                },
            ),
            "/ObsValue": xr.Dataset(
                {
                    "temperature": ("Location", temperature, {"units": "K"}),
                    "brightnessTemperature": (
                        ("Location", "Channel"),
                        temperature[:, None] + channels[None, :],
                        {"units": "K"},
                    ),
                }
            ),
        }
    )
    data_manager.put("globe", globe)

    yield

    shutil.rmtree(geode_config.data_lake.full_base_path, ignore_errors=True)
