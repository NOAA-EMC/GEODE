from geode.ingest.ingestors.bufr_ingestor import BufrIngestor


class SynopIngestor(BufrIngestor):
    def __init__(self):
        super().__init__("synop.yaml")
        self.data_type = "synop"
