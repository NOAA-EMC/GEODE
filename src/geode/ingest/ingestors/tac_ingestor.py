import xarray as xr

from geode.ingest.ingestors.base_ingestor import BaseIngestor


class TacIngestor(BaseIngestor):
    """Base ingestor for Traditional Alphanumeric Code (TAC) ASCII text reports."""

    def __init__(self, data_type: str):
        super().__init__(data_type)

    def _process(self, file_path: str) -> xr.DataTree | dict[str, xr.DataTree]:
        # TODO: parse the ASCII TAC report at file_path and convert it to an xr.DataTree
        raise NotImplementedError("TAC parsing not yet implemented.")
