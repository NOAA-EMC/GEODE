import yaml

from .config_base import ConfigBase, StrField, Optional, IntField


class MqttConfig(ConfigBase):
    broker_address = Optional(StrField(), default="wis2node.globaldata.nws.noaa.gov")
    broker_port = Optional(IntField(), default=8883)
    topic = Optional(StrField(), default="origin/a/wis2/us-noaa-nws/data/core/weather/#")
    download_dir = StrField()


class GeodeConfig(ConfigBase):
    mqtt = MqttConfig()

    def __init__(self, config_path: str):
        super().__init__()
        with open(config_path) as config_file:
            self.load(yaml.safe_load(config_file))
