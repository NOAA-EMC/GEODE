import os

from geode.configs.geode_config import geode_config
from geode.ingest.ingestors.bufr_ingestor import BufrIngestor


class TempIngestor(BufrIngestor):
    def __init__(self):
        super().__init__("temp.yaml")
        self.data_type = "temp"
