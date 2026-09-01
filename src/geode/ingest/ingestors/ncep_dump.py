from geode.ingest.ingestors import register
from geode.ingest.ingestors.obsbuilder_ingestor import ObsBuilderIngestor


@register("ncep_dump/atms")
class AtmsIngestor(ObsBuilderIngestor):
    def __init__(self):
        from spoc.dump.scripts.atmosphere.radiance_atms import BufrAtmsObsBuilder
        super().__init__("atms", BufrAtmsObsBuilder())

@register("ncep_dump/cris-fsr")
class CrisFsrIngestor(ObsBuilderIngestor):
    def __init__(self):
        from spoc.dump.scripts.atmosphere.radiance_cris import BufrCrisObsBuilder
        super().__init__("cris", BufrCrisObsBuilder())

# @register("ncep_dump/cris")
# class AtmsIngestor(ObsBuilderIngestor):
#     from spoc.dump.scripts.atmosphere.radiance_atms import BufrAtmsObsBuilder
#     def __init__(self):
#         super().__init__("atms", BufrAtmsObsBuilder())


# @register("ncep_dump/temp")
# class TempIngestor(SpocIngestor):
#     def __init__(self):
#         super().__init__("temp", "temp.yaml")
