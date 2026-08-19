import os

import yaml

from geode.configs.config_base import (
    BoolField,
    Choices,
    ConfigBase,
    IntField,
    Optional,
    ResolvedPathField,
    StrField,
)

ConfigDir = os.path.realpath(
    os.path.join(os.path.dirname(__file__), "..", "..", "..", "configs")
)

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


class BufrConfig(ConfigBase):
    table_path = ResolvedPathField()

    @property
    def map_dir(self) -> str:
        return os.path.join(ConfigDir, "bufr")


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


# Main Configuration Class


class GeodeConfig(ConfigBase):
    root_dir = ResolvedPathField()
    run_for_num_sec = Optional(IntField(), default=None)
    database = Choices({"sqlite": SqliteConfig(root_dir=root_dir)})
    data_lake = Choices(
        {
            "zarr": ZarrLakeConfig(root_dir=root_dir),
            "icechunk": IceChunkLakeConfig(root_dir=root_dir),
            "netcdf": NetCDFLakeConfig(root_dir=root_dir),
        }
    )
    wis2 = Wis2Config(root_dir=root_dir)
    bufr = BufrConfig()

    def __init__(self, config_path: str):
        super().__init__()
        with open(config_path) as config_file:
            self.load(yaml.safe_load(config_file))


# create singleton instance of GeodeConfig on module load
geode_config = GeodeConfig(os.path.join(ConfigDir, "geode_config.yaml"))
os.makedirs(geode_config.root_dir, exist_ok=True)
