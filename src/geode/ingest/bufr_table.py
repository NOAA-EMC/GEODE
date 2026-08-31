"""Utilities for looking up BUFR Table B descriptors."""

import csv
from pathlib import Path


class BufrTableB:
    """Provide descriptor metadata from BUFR Table B.

    Parameters
    ----------
    table_path : str | Path
        Path to a WMO BUFR/CREX Table B CSV file.

    Examples
    --------
    >>> table = BufrTableB("BUFRCREX_TableB_en.txt")
    >>> table.entry("001003")["ElementName_en"]
    'WMO Region number/geographical area'
    """

    def __init__(self, table_path: str | Path) -> None:
        self._descriptors = self._read_descriptors(Path(table_path))

    @staticmethod
    def _read_descriptors(table_path: Path) -> dict[str, dict[str, str]]:
        """Read FXY-to-row mappings from a Table B CSV file.

        Parameters
        ----------
        table_path : Path
            Path to the Table B CSV file.

        Returns
        -------
        dict[str, dict[str, str]]
            Mapping from six-digit FXY descriptors to complete Table B rows.

        Raises
        ------
        ValueError
            If a required Table B column is absent or an FXY value is invalid.
        """
        with table_path.open(newline="", encoding="utf-8") as table_file:
            reader = csv.DictReader(table_file)
            required_columns = {"FXY", "ElementName_en"}
            if reader.fieldnames is None or not required_columns <= set(reader.fieldnames):
                raise ValueError("BUFR Table B must contain FXY and ElementName_en columns.")

            descriptors: dict[str, dict[str, str]] = {}
            for row in reader:
                fxy = row["FXY"]
                if fxy is None or not fxy.isdigit() or len(fxy) != 6:
                    raise ValueError(f"Invalid BUFR Table B FXY value: {fxy!r}")
                descriptors[fxy] = dict(row)

        return descriptors

    def entry(self, fxy: str) -> dict[str, str]:
        """Return the complete Table B entry for an FXY descriptor.

        Parameters
        ----------
        fxy : str
            Six-digit BUFR FXY descriptor.

        Returns
        -------
        dict[str, str]
            A copy of the Table B row keyed by CSV column name.

        Raises
        ------
        KeyError
            If the descriptor is not in the loaded Table B file.
        ValueError
            If the descriptor is not a six-digit numeric FXY value.
        """
        if not fxy.isdigit() or len(fxy) != 6:
            raise ValueError(f"FXY must be a six-digit numeric value, got {fxy!r}.")

        return self._descriptors[fxy].copy()