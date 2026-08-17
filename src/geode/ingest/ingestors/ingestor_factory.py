from geode.ingest.ingestors.synop_ingestor import SynopIngestor
from geode.ingest.ingestors.temp_ingestor import TempIngestor

ingestors = {
    "surface-based-observations/temp": TempIngestor,
    "surface-based-observations/synop": SynopIngestor,
}

def get_ingestor(id: str) -> type | None:
    """Returns the appropriate ingestor class for a given an ID."""
    if id in ingestors.keys():
        return ingestors[id]
    else:
        print(f"[-] No ingestor found for ID: {id}")
        return None
