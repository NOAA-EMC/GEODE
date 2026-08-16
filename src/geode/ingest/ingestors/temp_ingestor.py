import os
import bufr
import xarray as xr

from geode.configs.geode_config import geode_config
from geode.ingest.ingestors.bufr_ingestor import BufrIngestor



class TempIngestor(BufrIngestor):
    def __init__(self):
        super().__init__("ship.yaml")
    


if __name__ == "__main__":
    ingestor = TempIngestor()
