from geode.ingest.ingestors import register
from geode.ingest.ingestors.obsbuilder_ingestor import ObsBuilderIngestor


@register("ncep_dump/atms")
class AtmsIngestor(ObsBuilderIngestor):
    def __init__(self):
        from spoc.dump.scripts.atmosphere.radiance_atms import BufrAtmsObsBuilder

        super().__init__("atms", BufrAtmsObsBuilder())


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
