import os
import tempfile

import bufr
import xarray as xr

from geode.configs.geode_config import geode_config
from geode.ingest.ingestors.base_ingestor import BaseIngestor


def container_to_xarray(
    container: bufr.DataContainer, description: bufr.encoders.Description
) -> xr.DataTree:

    # Use the NetCDF encoder as a bridge to XArray for now.
    encoder = bufr.encoders.netcdf.Encoder(description)
    print("[*] JJJJJJJJJ")
    with tempfile.NamedTemporaryFile(delete=True) as named_temp:
        print(f"[*] MMMMMMMMMM {named_temp.name} {encoder} {encoder.encoder}")
        encoder.encode(container, named_temp.name, False)
        print("[*] KKKKKKKKK")
        datatree = xr.open_datatree(named_temp.name)
        print("[*] LLLLLLLL")

    return datatree


class BufrIngestor(BaseIngestor):
    def __init__(self, bufr_yaml: str):
        super().__init__()
        self.bufr_yaml = os.path.join(geode_config.bufr.map_dir, bufr_yaml)
        self.table_path = geode_config.bufr.table_path

    def _process(self, file_path: str) -> xr.DataTree:
        print("[*] HHHHHHHHH")
        container = bufr.Parser(file_path, self.bufr_yaml, self.table_path).parse()
        print("[*] IIIIIIIIII")
        return container_to_xarray(container, bufr.encoders.Description(self.bufr_yaml))
