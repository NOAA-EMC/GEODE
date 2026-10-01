from pathlib import Path

import xarray as xr

from geode.ingest.ingestors.base_ingestor import BaseIngestor


class TacIngestor(BaseIngestor):
    """Base ingestor for Traditional Alphanumeric Code (TAC) ASCII text reports."""

    def __init__(self, data_type: str):
        super().__init__(data_type)

    def _process(self, file_path: str) -> xr.DataTree | dict[str, xr.DataTree]:
        """Read a TAC file and pass its text to the format-specific parser.

        Parameters
        ----------
        file_path : str
            Path to the ASCII TAC input file.

        Returns
        -------
        xarray.DataTree | dict[str, xarray.DataTree]
            Parsed report data.

        Examples
        --------
        Format-specific ingestors implement ``_parse`` for their TAC grammar.
        """
        report_text = Path(file_path).read_text(encoding="ascii")
        return self._parse(report_text)

    def _parse(self, report_text: str) -> xr.DataTree | dict[str, xr.DataTree]:
        """Parse TAC text using the selected report format.

        Parameters
        ----------
        report_text : str
            ASCII TAC report or bulletin text.

        Returns
        -------
        xarray.DataTree | dict[str, xarray.DataTree]
            Parsed report data.

        Examples
        --------
        Subclasses should delegate to a format-specific parser.
        """
        raise NotImplementedError("TAC subclasses must implement _parse().")
