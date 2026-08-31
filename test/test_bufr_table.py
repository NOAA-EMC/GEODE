from ast import literal_eval
from pathlib import Path

import pytest

from geode.admin import main
from geode.ingest.bufr_table import BufrTableB

TABLE_B_PATH = (
    Path(__file__).resolve().parents[1]
    / "parm"
    / "wmo-bufr4"
    / "txt"
    / "BUFRCREX_TableB_en.txt"
)


def test_entry_returns_complete_table_b_row() -> None:
    """Return the original metadata for an FXY descriptor."""
    table = BufrTableB(TABLE_B_PATH)

    assert table.entry("001003") == {
        "ClassNo": "01",
        "ClassName_en": "Identification",
        "FXY": "001003",
        "ElementName_en": "WMO Region number/geographical area",
        "BUFR_Unit": "Code table",
        "BUFR_Scale": "0",
        "BUFR_ReferenceValue": "0",
        "BUFR_DataWidth_Bits": "3",
        "CREX_Unit": "Code table",
        "CREX_Scale": "0",
        "CREX_DataWidth_Char": "1",
        "Note_en": "",
        "noteIDs": "",
        "Status": "Operational",
    }


def test_entry_rejects_invalid_fxy() -> None:
    """Reject malformed descriptor identifiers before a lookup occurs."""
    table = BufrTableB(TABLE_B_PATH)

    with pytest.raises(ValueError, match="six-digit"):
        table.entry("1003")


def test_info_bufr_prints_table_b_entry(capsys: pytest.CaptureFixture[str]) -> None:
    """Print the requested complete Table B entry to standard output."""
    main(["info", "bufr", "001003"])

    assert literal_eval(capsys.readouterr().out) == BufrTableB(TABLE_B_PATH).entry(
        "001003"
    )