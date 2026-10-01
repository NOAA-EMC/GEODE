import xarray as xr

from geode.ingest.ingestors import register
from geode.ingest.ingestors.tac_ingestor import TacIngestor
from geode.ingest.ingestors.temp_parser import TempParser


@register("tac/temp")
class TempIngestor(TacIngestor):
    """Ingest WMO TEMP reports from ASCII TAC files."""

    def __init__(self):
        super().__init__("temp")

    def _parse(self, report_text: str) -> xr.DataTree:
        """Parse the TEMP section structure from a TAC bulletin.

        Parameters
        ----------
        report_text : str
            ASCII TEMP report or bulletin text.

        Returns
        -------
        xarray.DataTree
            Data tree containing one child dataset per TEMP section.

        Examples
        --------
        The returned child datasets retain the section's coded groups.
        """
        return TempParser().parse(report_text)
