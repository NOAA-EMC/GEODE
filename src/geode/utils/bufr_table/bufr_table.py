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
            if reader.fieldnames is None or not required_columns <= set(
                reader.fieldnames
            ):
                raise ValueError(
                    "BUFR Table B must contain FXY and ElementName_en columns."
                )

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


class BufrCodeFlag:
    """Provide code and flag metadata from WMO BUFR tables.

    Parameters
    ----------
    table_path : str | Path
        Path to a WMO BUFR/CREX CodeFlag CSV file.

    Examples
    --------
    >>> table = BufrCodeFlag("BUFRCREX_CodeFlag_en.txt")
    >>> table.entry("001003", "1")["EntryName_en"]
    'Region I'
    """

    def __init__(self, table_path: str | Path) -> None:
        self._entries = self._read_entries(Path(table_path))

    @staticmethod
    def _read_entries(table_path: Path) -> dict[tuple[str, str], dict[str, str]]:
        """Read FXY-and-code-figure mappings from a CodeFlag CSV file.

        Parameters
        ----------
        table_path : Path
            Path to the CodeFlag CSV file.

        Returns
        -------
        dict[tuple[str, str], dict[str, str]]
            Mapping from FXY and code figure pairs to complete CodeFlag rows.

        Raises
        ------
        ValueError
            If a required CodeFlag column is absent or an FXY value is invalid.
        """
        with table_path.open(newline="", encoding="utf-8") as table_file:
            reader = csv.DictReader(table_file)
            required_columns = {"FXY", "CodeFigure"}
            if reader.fieldnames is None or not required_columns <= set(
                reader.fieldnames
            ):
                raise ValueError(
                    "CodeFlag table must contain FXY and CodeFigure columns."
                )

            entries: dict[tuple[str, str], dict[str, str]] = {}
            for row in reader:
                fxy = row["FXY"]
                if fxy is None or not fxy.isdigit() or len(fxy) != 6:
                    raise ValueError(f"Invalid BUFR CodeFlag FXY value: {fxy!r}")
                code_figure = row["CodeFigure"]
                if code_figure is None:
                    raise ValueError(
                        "CodeFlag table contains a missing CodeFigure value."
                    )
                entries[(fxy, code_figure)] = dict(row)

        return entries

    def entry(self, fxy: str, code_figure: str) -> dict[str, str]:
        """Return the CodeFlag entry for an FXY descriptor and code figure.

        Parameters
        ----------
        fxy : str
            Six-digit BUFR FXY descriptor.
        code_figure : str
            Code figure exactly as represented in the CodeFlag table.

        Returns
        -------
        dict[str, str]
            A copy of the CodeFlag row keyed by CSV column name.

        Raises
        ------
        KeyError
            If the FXY and code figure pair is not in the loaded CodeFlag file.
        ValueError
            If the descriptor is not a six-digit numeric FXY value.
        """
        if not fxy.isdigit() or len(fxy) != 6:
            raise ValueError(f"FXY must be a six-digit numeric value, got {fxy!r}.")

        return self._entries[(fxy, code_figure)].copy()

