

import sys, os
import yaml

from geode.configs.config_base import ConfigBase, \
                                      StrField, \
                                      Optional, \
                                      IntField, \
                                      BoolField, \
                                      ListField, \
                                      Choices

ConfigDir = os.path.realpath(
    os.path.join(os.path.dirname(__file__), "..", "..", "..", "configs"))

class Wis2IngestorConfig(ConfigBase):
    wis_id = StrField()
    name = StrField()
    module = StrField()

class Wis2Config(ConfigBase):
    broker_address = Optional(StrField(), default="wis2node.globaldata.nws.noaa.gov")
    broker_port = Optional(IntField(), default=8883)
    use_websockets = Optional(BoolField(), default=False)
    topic = Optional(StrField(), default="origin/a/wis2/us-noaa-nws/data/core/weather/#")
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


class SqliteConfig(ConfigBase):
    db_path = StrField()

    def __init__(self, root_dir: str):
        super().__init__()
        self.root_dir = root_dir

    @property
    def full_db_path(self) -> str:
        return os.path.join(self.root_dir, self.db_path)


class DataLakeConfig(ConfigBase):
    dir = StrField()
    format = Choices({"netcdf", "zarr", "icechunk"})
    split_by = Choices({"year", "month", "day"})
    filename_template = StrField()  

    def __init__(self, root_dir: str):
        super().__init__()
        self.root_dir = root_dir

    @property
    def full_dir(self) -> str:
        return os.path.join(self.root_dir, self.dir)


class BufrConfig(ConfigBase):
    table_path = StrField()

    @property
    def map_dir(self) -> str:
        return os.path.join(ConfigDir, "bufr")


class GeodeConfig(ConfigBase):
    root_dir = StrField()
    debug = Optional(BoolField(), default=False)
    database = Choices({"sqlite": SqliteConfig(root_dir=root_dir)}
                        # "postgres": PostgresConfig()  # Uncomment if Postgres support is added
                        )
    data_lake = DataLakeConfig(root_dir=root_dir)
    wis2 = Wis2Config(root_dir=root_dir)
    bufr = BufrConfig()

    def __init__(self, config_path: str):
        super().__init__()
        with open(config_path) as config_file:
            self.load(yaml.safe_load(config_file))


# create singleton instance of GeodeConfig on module load
geode_config = GeodeConfig(os.path.join(ConfigDir, "geode_config.yaml"))
