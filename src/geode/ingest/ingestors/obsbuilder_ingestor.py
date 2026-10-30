import bufr
import xarray as xr
from bufr.obs_builder import ObsBuilder

from geode.ingest.ingestors.base_ingestor import BaseIngestor
from geode.ingest.ingestors.bufr_ingestor import container_to_xarray

IndexCoord = "dateTime"
LocationCoords = ["latitude", "longitude"]
MetaDataGroup = "MetaData"
PromotedCoords = ["dateTime", "latitude", "longitude"]


class ObsBuilderIngestor(BaseIngestor):
    def __init__(self, data_type: str, obs_builder: ObsBuilder, is_sorted: bool = True):
        super().__init__(data_type, is_sorted=is_sorted)
        self.obs_builder = obs_builder

    def _process(self, file_path: str) -> xr.DataTree | dict[str, xr.DataTree]:
        comm = bufr.mpi.Comm("world")
        container = self.obs_builder.make_obs(comm, file_path)
        container.gather(comm)

        if comm.rank() == 0:
            self.obs_builder.finalize_container(container)
            datatree = container_to_xarray(container, self.obs_builder.description)
            d = self._promote_coords(datatree)
            return d

        return None

    def _promote_coords(
        self, data: xr.DataTree | dict[str, xr.DataTree]
    ) -> xr.DataTree | dict[str, xr.DataTree]:
        def _promote(ds: xr.Dataset) -> xr.Dataset:
            if all(name in ds.variables for name in PromotedCoords):
                return ds.set_coords(PromotedCoords).set_xindex(IndexCoord)
            return ds

        if isinstance(data, xr.DataTree):
            return data.map_over_datasets(_promote)
        return {key: tree.map_over_datasets(_promote) for key, tree in data.items()}
