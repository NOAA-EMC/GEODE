from geode.ingest.ingestors.base_ingestor import BaseIngestor

import os
import bufr
import xarray as xr

from geode.configs.geode_config import geode_config
# from geode.lake.lake_manager import lake_manager


def container_to_xarray(container: bufr.DataContainer, 
                        description: bufr.encoders.Description) -> xr.DataTree:

    def get_description_var(field_name: str):
        for var in description.get_variables():
            if field_name == os.path.split(var["source"])[-1]:
                return var

    datatree = xr.DataTree()
    for field_name in container.list():
        var = get_description_var(field_name)
        print (f"Processing field: {field_name}, Description: {var}")
        if var is not None:
            # Get the data from the container and create a DataArray
            data = container.get(field_name)
            datatree[var["name"]] = xr.DataArray(data=data)
            
            # Add attributes to the DataArray
            for key, value in var.items():
                if key != "name":
                    datatree[var["name"]].attrs[key] = value
            
    return datatree
    

class BufrIngestor(BaseIngestor):
    def __init__(self, bufr_yaml: str):
        super().__init__()
        self.bufr_yaml = os.path.join(geode_config.bufr.map_dir, bufr_yaml)
        self.table_path = geode_config.bufr.table_path

    def _process(self, file_path: str) -> xr.DataTree:
        container = bufr.Parser(file_path, self.bufr_yaml, self.table_path).parse()
        return container_to_xarray(container, bufr.encoders.Description(self.bufr_yaml))
