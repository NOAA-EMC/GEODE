from geode.ingest.ingestors import register
from geode.ingest.ingestors.bufr_ingestor import BufrIngestor


@register("wis2/surface-based-observations/synop")
class SynopIngestor(BufrIngestor):
    def __init__(self):
        super().__init__("synop", "synop.yaml")


@register("wis2/surface-based-observations/temp")
class TempIngestor(BufrIngestor):
    def __init__(self):
        super().__init__("temp", "temp.yaml")
