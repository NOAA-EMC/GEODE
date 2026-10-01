from pathlib import Path

import pytest

from geode.ingest.consumers import tac_gts_reader
from geode.ingest.ingestors.tac_gts import TempIngestor
from geode.ingest.ingestors.tac_ingestor import TacIngestor
from geode.ingest.ingestors.temp_parser import TempParser

TEMP_REPORT = """583
USUS04 KWBC 301800
TTAA 80181 72365 99834 17256 22507 00031 ///// ///// 92718 /////
///// 85452 ///// ///// 70068 03634 23013 50572 12558 19513 40739
23358 21025 30946 29375 20047 25074 35373 21558 20228 42172 21563
15417 54967 21554 10668 66562 26017 88999 77233 21572 41809 31313
45408 81702 51515 10164 00000 10194 ///// 20513=
TTAA 80181 72451 99915 19400 13013 00012 ///// ///// 92696 /////
///// 85423 17400 16041 70066 09400 18542 50579 03902 20032 40753
13715 21529 30965 28970 21533 25093 38970 21050 20242 49774 22059
15425 61769 24568 10671 69365 22013 88999 77152 24569 41416 31313
44108 81703=
"""


def test_tac_gts_reader_dispatches_file(tmp_path, monkeypatch):
    """Verify that the TAC GTS consumer dispatches a report to its ingestor.

    Parameters
    ----------
    tmp_path : pathlib.Path
        Temporary directory for the TAC report fixture.
    monkeypatch : pytest.MonkeyPatch
        Fixture used to intercept the ingestor processing boundary.

    Returns
    -------
    None

    Examples
    --------
    Run with ``pytest test/test_tac_gts_reader.py``.
    """
    report_text = TEMP_REPORT
    report_path = tmp_path / "temp.tac"
    report_path.write_text(report_text, encoding="ascii")
    processed_reports = []

    def capture_process(ingestor: TacIngestor, file_path: str) -> None:
        processed_reports.append(
            (ingestor.data_type, Path(file_path).read_text(encoding="ascii"))
        )

    monkeypatch.setattr(TacIngestor, "process", capture_process)

    reader = tac_gts_reader.TacGTSReader()
    reader.ingest("temp", [str(report_path)])

    assert processed_reports == [("temp", report_text)]


def test_temp_parser_extracts_sections_from_bulletin():
    """Verify TEMP section headers and coded groups are retained in xarray.

    Parameters
    ----------
    None

    Returns
    -------
    None

    Examples
    --------
    Run with ``pytest test/test_tac_gts_reader.py``.
    """
    data_tree = TempParser().parse(TEMP_REPORT)

    assert data_tree.attrs["section_count"] == 2
    first_section = data_tree["section_000001"].dataset
    second_section = data_tree["section_000002"].dataset
    assert first_section.attrs["section_code"] == "TTAA"
    assert first_section.attrs["time_group"] == "80181"
    assert first_section.attrs["station_id"] == "72365"
    assert first_section.attrs["decoded_level_count"] == 12
    assert first_section["code_group"].isel(group=0).item() == "99834"
    assert first_section["pressure"].sel(level=983.4).item() == pytest.approx(983.4)
    assert first_section["dewPointTemperature"].sel(
        level=983.4
    ).item() == pytest.approx(284.35)
    assert first_section["pressure"].sel(level=700.0).item() == pytest.approx(700.0)
    assert first_section["temperature"].sel(level=700.0).item() == pytest.approx(276.75)
    assert first_section["dewPointTemperature"].sel(
        level=700.0
    ).item() == pytest.approx(273.35)
    assert first_section["windDirection"].sel(level=700.0).item() == pytest.approx(
        230.0
    )
    assert first_section["windSpeed"].sel(level=700.0).item() == pytest.approx(
        13 * 0.514444
    )
    assert second_section.attrs["station_id"] == "72451"


def test_temp_parser_decodes_negative_temperature_and_large_depression():
    """Verify sign and high-depression coding for TEMP temperature groups.

    Parameters
    ----------
    None

    Returns
    -------
    None

    Examples
    --------
    Run with ``pytest test/test_tac_gts_reader.py``.
    """
    temperature, dew_point = TempParser._decode_temperature_group("56256")

    assert temperature == pytest.approx(266.95)
    assert dew_point == pytest.approx(260.95)


def test_temp_parser_represents_calm_wind_direction_as_missing():
    """Verify a calm TEMP wind group has zero speed and undefined direction.

    Parameters
    ----------
    None

    Returns
    -------
    None

    Examples
    --------
    Run with ``pytest test/test_tac_gts_reader.py``.
    """
    direction, speed = TempParser._decode_wind_group("00000", "80180")

    assert direction is None
    assert speed == 0.0


def test_temp_ingestor_reads_and_parses_file(tmp_path):
    """Verify the TEMP ingestor reads TAC text and returns parsed xarray data.

    Parameters
    ----------
    tmp_path : pathlib.Path
        Temporary directory for the TAC report fixture.

    Returns
    -------
    None

    Examples
    --------
    Run with ``pytest test/test_tac_gts_reader.py``.
    """
    report_path = tmp_path / "temp.tac"
    report_path.write_text(TEMP_REPORT, encoding="ascii")

    data_tree = TempIngestor()._process(str(report_path))
    print(data_tree)

    assert data_tree["section_000001"].dataset.attrs["station_id"] == "72365"
