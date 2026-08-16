from geode.ingest.ingestors.synop_ingestor import SynopIngestor
from geode.ingest.ingestors.temp_ingestor import TempIngestor

ingestors = {
    # "surface-based-observations/temp": TempIngestor,
    "surface-based-observations/synop": SynopIngestor,
}

def get_ingestor(wis_id: str) -> type | None:
    """Returns the appropriate ingestor class for a given WIS ID."""
    if wis_id in ingestors.keys():
        return ingestors[wis_id]
    else:
        print(f"[-] No ingestor found for WIS ID: {wis_id}")
        return None
