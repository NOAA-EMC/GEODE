import os
import yaml

from geode.configs.config_base import ConfigBase
from geode.configs.config_base import StrField, IntField, ListField, Optional
from geode.configs.geode_config import ConfigDir


class DataTypeConfig(ConfigBase):
    id = StrField()
    path_template = StrField()
    num_tasks = Optional(IntField(), default=1)
    batch_days = Optional(IntField(), default=1)
    memory = Optional(StrField(), default=None)

    def __init__(self, hours):
        self.hours = hours

    @property
    def paths(self) -> list[str]:
        return [self.path_template.format(hour=hour) for hour in self.hours]


class DumpConfig(ConfigBase):
    hours = Optional(ListField(StrField()), default=["00", "06", "12", "18"])
    data_types = ListField(DataTypeConfig(hours=hours))

    def __init__(self, config_path: str):
        super().__init__()
        with open(config_path) as config_file:
            self.load(yaml.safe_load(config_file))

    def get_file_paths(self, dump_id: str) -> list[str]:
        for data_type in self.data_types:
            if data_type.id == dump_id:
                break
        else:
            raise ValueError(f"No path template found for BUFR dump ID: {dump_id}")

        return [data_type.path_template.format(hour=hour) for hour in self.hours]


# create singleton instance of DumpConfig on module load
dump_config = DumpConfig(os.path.join(ConfigDir, "ncep_dump.yaml"))
