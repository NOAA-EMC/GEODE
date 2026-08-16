
from geode.configs.geode_config import geode_config

class LakeManager:
    def __init__(self):
        self.lake = geode_config.lake

    def add(self, data_tree):
        raise NotImplementedError("This method should be implemented by subclasses.")


class IceChunkLakeManager(LakeManager):
    def __init__(self):
        super().__init__()
        # Additional initialization for IceChunkLakeManager if needed

    def add(self, data_tree):
        # Implement the logic to add data_tree to IceChunk lake
        pass


class ZarrLakeManager(LakeManager):
    def __init__(self):
        super().__init__()
        # Additional initialization for ZarrLakeManager if needed

    def add(self, data_tree):
        # Implement the logic to add data_tree to Zarr lake
        pass


class NetCDFLakeManager(LakeManager):
    def __init__(self):
        super().__init__()
        # Additional initialization for NetCDFLakeManager if needed

    def add(self, data_tree):
        # Implement the logic to add data_tree to NetCDF lake
        pass


manager_mapping = {
    "icechunk": IceChunkLakeManager,
    "zarr": ZarrLakeManager,
    "netcdf": NetCDFLakeManager
}

def get_lake_manager():
    lake_manager_class = manager_mapping.get(geode_config.lake.type.lower())
    if lake_manager_class is None:
        raise ValueError(f"Unsupported lake type: {geode_config.lake.type}")
    return lake_manager_class()

lake_manager = get_lake_manager()