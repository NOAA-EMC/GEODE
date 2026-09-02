import os
import shutil
from datetime import datetime

import yaml

from geode.configs import GeodeConfigPath, PackageConfigDir
from geode.configs.config_base import (
    BoolField,
    Choices,
    ConfigBase,
    IntField,
    Optional,
    ResolvedPathField,
    StrField,
)
from geode.configs.ncep_dump_config import dump_config

# Ingestor Configuration


class Wis2IngestorConfig(ConfigBase):
    wis_id = StrField()
    name = StrField()
    module = StrField()


class Wis2Config(ConfigBase):
    broker_address = Optional(StrField(), default="wis2node.globaldata.nws.noaa.gov")
    broker_port = Optional(IntField(), default=8883)
    use_websockets = Optional(BoolField(), default=False)
    topic = Optional(
        StrField(), default="origin/a/wis2/us-noaa-nws/data/core/weather/#"
    )
    download_dir = StrField()

    def __init__(self, root_dir: str):
        super().__init__()
        self.root_dir = root_dir

    @property
    def full_download_dir(self) -> str:
        return os.path.join(self.root_dir, self.download_dir)

    @property
    def broker_url(self) -> str:
        protocol = "wss" if self.use_websockets else "ssl"
        return f"{protocol}://everyone:everyone@{self.broker_address}:{self.broker_port}/mqtt"


@staticmethod
def _find_table_path() -> str:
    gettab_path = shutil.which("gettab")
    if gettab_path is None:
        raise FileNotFoundError(
            "gettab path could not be found. Please ensure it is installed and in your PATH."
        )

    return os.path.realpath(os.path.join(gettab_path, "..", "..", "tables"))


class BufrConfig(ConfigBase):
    table_path = Optional(ResolvedPathField(), default=_find_table_path())

    @property
    def map_dir(self) -> str:
        return os.path.join(PackageConfigDir, "bufr")


# Database Configuration


class SqliteConfig(ConfigBase):
    db_path = StrField()

    def __init__(self, root_dir: str):
        super().__init__()
        self.root_dir = root_dir

    @property
    def full_db_path(self) -> str:
        return os.path.join(self.root_dir, self.db_path)


# DataLake Configuration


class LakeConfig(ConfigBase):
    base_dir = StrField()

    def __init__(self, root_dir: str):
        super().__init__()
        self.root_dir = root_dir

    @property
    def full_base_path(self) -> str:
        return os.path.join(self.root_dir, self.base_dir)


class ZarrLakeConfig(LakeConfig):
    chunk_size = Optional(IntField(), default=5000)
    split_by = Optional(Choices({"year", "month", "day", "none"}), default="none")


class IceChunkLakeConfig(LakeConfig):
    pass


class NetCDFLakeConfig(LakeConfig):
    split_by = Choices({"year", "month", "day"})


# NCEP DUMP Configuration

class NcepDumpConfig(ConfigBase):
    root_path = StrField()

    def get_file_paths(self, dump_id: str, day: datetime) -> list[str]:
        src_path = os.path.join(self.root_path, f"gdas.{day.strftime('%Y%m%d')}")
        rel_paths =  dump_config.get_file_paths(dump_id)
        return [os.path.join(src_path, rel_path) for rel_path in rel_paths]


# Main Configuration Class

class GeodeConfig(ConfigBase):
    root_dir = ResolvedPathField()
    run_for_num_sec = Optional(IntField(), default=None)
    # database = Choices({"sqlite": SqliteConfig(root_dir=root_dir)})  # Future
    data_lake = Choices(
        {
            "zarr": ZarrLakeConfig(root_dir=root_dir),
            "icechunk": IceChunkLakeConfig(root_dir=root_dir),
            "netcdf": NetCDFLakeConfig(root_dir=root_dir),
        }
    )
    wis2 = Wis2Config(root_dir=root_dir)
    ncep_dump = NcepDumpConfig()
    bufr = BufrConfig()

    def __init__(self, config_path: str):
        super().__init__()
        with open(config_path) as config_file:
            self.load(yaml.safe_load(config_file))


# create singleton instance of GeodeConfig on module load
geode_config = GeodeConfig(GeodeConfigPath)
os.makedirs(geode_config.root_dir, exist_ok=True)
