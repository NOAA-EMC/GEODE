import os
import bufr
import xarray as xr

from configs.geode_config import GeodeConfig

bufrMappingDir = os.path.join(os.path.dirname(__file__), "../configs/bufr_mappings")


def container_to_xarray(container: bufr.Container, 
                        description: bufr.encoders.Description) -> xr.DataTree:

    def get_description_var(field_name: str):
        for var in description.get_variables():
            if var.name == field_name:
                return var

    datatree = xr.DataTree()
    for field_name in container.list():
        var = get_description_var(field_name)
        if var is not None:
            # Get the data from the container and create a DataArray
            data = container.get(field_name)
            datatree[var["name"]] = xr.DataArray(data=data)
            
            # Add attributes to the DataArray
            for key, value in var.items():
                if key != "name":
                    datatree[var["name"]].attrs[key] = value
            
    return datatree


class ShipIngestor:
    def __init__(self, config: GeodeConfig):
        self.ship_yaml = os.path.join(bufrMappingDir, "ship.yaml")
        self.table_path = config.bufr_ingest.table_path
    
    def ingest(self, file_path: str) -> xr.DataTree:
        container = bufr.Parser(file_path, self.ship_yaml, self.table_path).parse()
        return container_to_xarray(container, bufr.encoders.Description(self.ship_yaml))
    


if __name__ == "__main__":
    from configs.geode_config import GeodeConfig
    config = GeodeConfig(os.path.join(os.path.dirname(__file__), "../configs/geode_config.yaml"))
    ingestor = ShipIngestor(config)
