import os
import tempfile

import bufr
import xarray as xr

from geode.configs.geode_config import geode_config
from geode.ingest.ingestors.base_ingestor import BaseIngestor


def container_to_xarray(
    container: bufr.DataContainer, description: bufr.encoders.Description
) -> xr.DataTree | dict[xr.DataTree]:
    
    # Use the NetCDF encoder as a bridge to XArray for now.
    encoder = bufr.encoders.netcdf.Encoder(description)

    categories = container.all_sub_categories()
    print ('##### categories:', categories)
    if len(categories) == 1 and len(categories[0]) == 0:
        with tempfile.NamedTemporaryFile(delete=True) as named_temp:
            encoder.encode(container, named_temp.name)
            datatree = xr.open_datatree(named_temp.name)
    else:
        datatree = {}
        with tempfile.TemporaryDirectory() as temp_dir:
            encoder.encode(container, os.path.join(temp_dir, 'data_{splits/satId}.nc'))

            # loop through the files in the temporary dir and add them to the datatree
            for file_name in os.listdir(temp_dir):
                if file_name.endswith(".nc"):
                    sub_type = file_name.replace("data_", "").replace(".nc", "")
                    datatree[sub_type] = xr.open_datatree(os.path.join(temp_dir, file_name))

    return datatree


class BufrIngestor(BaseIngestor):
    def __init__(self, data_type: str, bufr_yaml: str):
        super().__init__(data_type)
        self.bufr_yaml = os.path.join(geode_config.bufr.map_dir, bufr_yaml)
        self.table_path = geode_config.bufr.table_path

    def _process(self, file_path: str)  -> xr.DataTree | dict[xr.DataTree]:
        container = bufr.Parser(file_path, self.bufr_yaml, self.table_path).parse()
        return container_to_xarray(container, bufr.encoders.Description(self.bufr_yaml))
