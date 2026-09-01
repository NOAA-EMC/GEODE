import pprint
from ast import literal_eval
from pathlib import Path

import pytest

from geode.admin import main
from geode.utils.bufr_table import BufrCodeFlag, BufrTableB

TABLE_B_PATH = (
    Path(__file__).resolve().parents[1]
    / "parm"
    / "wmo-bufr4"
    / "txt"
    / "BUFRCREX_TableB_en.txt"
)
CODE_FLAG_PATH = (
    Path(__file__).resolve().parents[1]
    / "src"
    / "geode"
    / "data"
    / "resources"
    / "BUFRCREX_CodeFlag_en.txt"
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


def test_entry_returns_complete_code_flag_row() -> None:
    """Return the original CodeFlag metadata for an FXY and code figure."""
    table = BufrCodeFlag(CODE_FLAG_PATH)

    assert table.entry("001003", "1") == {
        "FXY": "001003",
        "ElementName_en": "WMO Region number/geographical area",
        "CodeFigure": "1",
        "EntryName_en": "Region I",
        "EntryName_sub1_en": "",
        "EntryName_sub2_en": "",
        "Note_en": "",
        "noteIDs": "",
        "Status": "Operational",
    }


def test_info_bufr_prints_table_b_entry(capsys: pytest.CaptureFixture[str]) -> None:
    """Print the requested complete Table B entry to standard output."""
    main(["info", "bufr", "001003"])

    assert literal_eval(capsys.readouterr().out) == BufrTableB(TABLE_B_PATH).entry(
        "001003"
    )


def test_info_bufr_prints_code_flag_entry(capsys: pytest.CaptureFixture[str]) -> None:
    """Print Table B and CodeFlag entries when a code figure is provided."""
    main(["info", "bufr", "001003", "1"])

    assert capsys.readouterr().out == (
        f"{pprint.pformat(BufrTableB(TABLE_B_PATH).entry('001003'), sort_dicts=False)}\n"
        f"{pprint.pformat(BufrCodeFlag(CODE_FLAG_PATH).entry('001003', '1'), sort_dicts=False)}\n"
    )
