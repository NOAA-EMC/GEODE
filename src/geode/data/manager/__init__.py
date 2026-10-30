from geode.configs.geode_config import geode_config
from geode.data.manager.icechunk import IceChunkDataManager
from geode.data.manager.netcdf import NetCDFDataManager
from geode.data.manager.zarr import ZarrDataManager

manager_mapping = {
    "icechunk": IceChunkDataManager,
    "zarr": ZarrDataManager,
    "netcdf": NetCDFDataManager,
}


def get_data_manager():
    data_manager_class = manager_mapping.get(geode_config.data_lake.type.lower())
    if data_manager_class is None:
        raise ValueError(f"Unsupported lake type: {geode_config.data_lake.type}")
    return data_manager_class()


data_manager = get_data_manager()
