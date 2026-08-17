from geode.ingest.ingestors.base_ingestor import BaseIngestor

import os
import bufr
import xarray as xr
import tempfile

from geode.configs.geode_config import geode_config


def container_to_xarray(container: bufr.DataContainer, 
                        description: bufr.encoders.Description) -> xr.DataTree:

    # Use the NetCDF encoder as a bridge to XArray for now.
    encoder = bufr.encoders.netcdf.Encoder(description)
    with tempfile.NamedTemporaryFile(delete=True) as named_temp:
        encoder.encode(container, named_temp.name, False).values()
        datatree = xr.open_datatree(named_temp.name)
        
    return datatree
    

class BufrIngestor(BaseIngestor):
    def __init__(self, bufr_yaml: str):
        super().__init__()
        self.bufr_yaml = os.path.join(geode_config.bufr.map_dir, bufr_yaml)
        self.table_path = geode_config.bufr.table_path

    def _process(self, file_path: str) -> xr.DataTree:
        container = bufr.Parser(file_path, self.bufr_yaml, self.table_path).parse()
        return container_to_xarray(container, bufr.encoders.Description(self.bufr_yaml))
