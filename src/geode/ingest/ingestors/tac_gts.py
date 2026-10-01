from geode.ingest.ingestors import register
from geode.ingest.ingestors.tac_ingestor import TacIngestor


@register("tac/temp")
class TempIngestor(TacIngestor):
    def __init__(self):
        super().__init__("temp")
