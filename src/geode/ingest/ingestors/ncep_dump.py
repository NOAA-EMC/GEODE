import bufr
import xarray as xr

from geode.ingest.ingestors import register
from geode.ingest.ingestors.bufr_ingestor import container_to_xarray
from geode.ingest.ingestors.obsbuilder_ingestor import ObsBuilderIngestor


@register("ncep_dump/atms")
class AtmsIngestor(ObsBuilderIngestor):
    def __init__(self):
        from spoc.dump.scripts.atmosphere.radiance_atms import BufrAtmsObsBuilder

        super().__init__("atms", BufrAtmsObsBuilder())


@register("ncep_dump/mhs")
class MhsIngestor(ObsBuilderIngestor):
    def __init__(self):
        from spoc.dump.scripts.atmosphere.radiance_mhs import MhsObsBuilder

        super().__init__("mhs", MhsObsBuilder())

    def _process(self, file_path: str) -> xr.DataTree | dict[xr.DataTree]:
        comm = bufr.mpi.Comm("world")
        container = self.obs_builder.make_obs(comm, {"1b": file_path})
        container.gather(comm)

        if comm.rank() == 0:
            self.obs_builder.finalize_container(container)
            datatree = container_to_xarray(container, self.obs_builder.description)
            return datatree

        return None


@register("ncep_dump/cris")
class CrisFsrIngestor(ObsBuilderIngestor):
    def __init__(self):
        from spoc.dump.scripts.atmosphere.radiance_crsfdp import BufrCrisObsBuilder

        super().__init__("cris", BufrCrisObsBuilder())


@register("ncep_dump/amsua")
class AmsuaIngestor(ObsBuilderIngestor):
    def __init__(self):
        from spoc.dump.scripts.atmosphere.radiance_amsua import BufrAmsuaObsBuilder

        super().__init__("amsua", BufrAmsuaObsBuilder())
