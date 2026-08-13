

import sys, os
if __name__ == "__main__":
    sys.path.append(os.path.abspath(os.path.join(os.path.dirname(os.path.dirname(__file__)), "..")))

import yaml

from geode.configs.config_base import ConfigBase, \
                                      StrField, \
                                      Optional, \
                                      IntField, \
                                      BoolField, \
                                      Choices


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

    def __init__(self, root_dir: str):
        super().__init__()
        self.root_dir = root_dir

    @property
    def full_dir(self) -> str:
        return os.path.join(self.root_dir, self.dir)


class BufrIngestConfig(ConfigBase):
    table_path = StrField()


class GeodeConfig(ConfigBase):
    root_dir = StrField()
    database = Choices({"sqlite": SqliteConfig(root_dir=root_dir)}
                        # "postgres": PostgresConfig()  # Uncomment if Postgres support is added
                        )
    data_lake = DataLakeConfig(root_dir=root_dir)
    wis2 = Wis2Config(root_dir=root_dir)
    bufr_ingest = BufrIngestConfig()

    def __init__(self, config_path: str):
        super().__init__()
        with open(config_path) as config_file:
            self.load(yaml.safe_load(config_file))


if __name__ == "__main__":
    config_path = os.path.join(os.path.dirname(__file__), "geode_config.yaml")
    geode_config = GeodeConfig(config_path)
    
    print(geode_config.wis2.full_download_dir)  # This will ensure the download directory exists
    print(geode_config.database.full_db_path)
    print(geode_config.data_lake.full_dir)  # This will ensure the data lake directory path is correct
