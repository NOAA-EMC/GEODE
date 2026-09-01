import os
import tempfile

import bufr
from bufr.obs_builder import ObsBuilder
import xarray as xr

from geode.configs.ncep_dump_config import dump_config
from geode.ingest.ingestors.base_ingestor import BaseIngestor
from geode.ingest.ingestors.bufr_ingestor import container_to_xarray


class ObsBuilderIngestor(BaseIngestor):
    def __init__(self, data_type: str, obs_builder: ObsBuilder):
        super().__init__(data_type)
        self.obs_builder = obs_builder

    def _process(self, file_path: str) -> xr.DataTree | dict[xr.DataTree]:
        comm = bufr.mpi.Comm("world")
        container = self.obs_builder.make_obs(comm, file_path)
        container.gather(comm)

        if comm.rank() == 0:
            self.obs_builder.finalize_container(container)
            datatree = container_to_xarray(container, self.obs_builder.description)
            return datatree

        return None
