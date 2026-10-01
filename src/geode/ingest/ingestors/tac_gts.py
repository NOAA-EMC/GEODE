from datetime import datetime

import xarray as xr

from geode.ingest.ingestors import register
from geode.ingest.ingestors.tac_ingestor import TacIngestor
from geode.ingest.ingestors.temp_parser import TempParser


@register("tac/temp")
class TempIngestor(TacIngestor):
    """Ingest WMO TEMP reports from ASCII TAC files."""

    def __init__(
        self,
        reference_datetime: datetime | None = None,
        include_raw_code: bool = False,
    ):
        super().__init__("temp")
        self.reference_datetime = reference_datetime
        self.include_raw_code = include_raw_code

    def _parse(self, report_text: str) -> dict[str, xr.DataTree]:
        """Decode TEMP observations using the configured time reference.

        Parameters
        ----------
        report_text : str
            ASCII TEMP report or bulletin text.

        Returns
        -------
        dict[str, xarray.DataTree]
            Trees keyed by ``surface`` and/or ``upper_air``, each with flat
            ``MetaData`` and ``ObsValue`` groups.

        Examples
        --------
        The reference timestamp is supplied when constructing the ingestor.
        """
        return TempParser().parse(
            report_text, self.reference_datetime, self.include_raw_code
        )
