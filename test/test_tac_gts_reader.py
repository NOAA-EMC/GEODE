from datetime import UTC, datetime
from pathlib import Path

import numpy as np
import pytest

from geode.ingest.consumers import tac_gts_reader
from geode.ingest.ingestors.tac_gts import TempIngestor
from geode.ingest.ingestors.tac_ingestor import TacIngestor
from geode.ingest.ingestors.temp_parser import (
    TempParser,
    _estimate_drift_positions,
    _Observation,
)

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
REFERENCE_DATETIME = datetime(2026, 9, 30, 18, tzinfo=UTC)


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
            (
                ingestor.data_type,
                Path(file_path).read_text(encoding="ascii"),
                ingestor.include_raw_code,
            )
        )

    monkeypatch.setattr(TacIngestor, "process", capture_process)

    reader = tac_gts_reader.TacGTSReader()
    reader.ingest("temp", [str(report_path)], REFERENCE_DATETIME, include_raw_code=True)

    assert processed_reports == [("temp", report_text, True)]


def test_temp_parser_decodes_flat_bufr_style_groups():
    """Verify flat BUFR-style metadata and observation groups are produced.

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
    data_trees = TempParser().parse(TEMP_REPORT, REFERENCE_DATETIME)

    assert set(data_trees) == {"surface", "upper_air"}
    surface_tree = data_trees["surface"]
    upper_air_tree = data_trees["upper_air"]
    surface_metadata = surface_tree["MetaData"].dataset
    surface_observations = surface_tree["ObsValue"].dataset
    metadata = upper_air_tree["MetaData"].dataset
    observations = upper_air_tree["ObsValue"].dataset
    assert surface_tree.attrs["observation_count"] == 2
    assert upper_air_tree.attrs["observation_count"] == 24
    assert surface_metadata.sizes["Location"] == 2
    assert surface_observations.sizes["Location"] == 2
    assert metadata.sizes["Location"] == 24
    assert observations.sizes["Location"] == 24
    assert set(metadata.data_vars) == {
        "dateTime",
        "receiptTime",
        "stationIdentification",
        "latitude",
        "longitude",
        "estimatedLatitude",
        "estimatedLongitude",
        "pressure",
        "height",
        "reportType",
    }
    assert all(
        variable.dims == ("Location",) for variable in metadata.data_vars.values()
    )
    assert all(
        variable.dims == ("Location",) for variable in observations.data_vars.values()
    )
    assert set(observations.data_vars) == {
        "temperature",
        "dewPointTemperature",
        "windEastward",
        "windNorthward",
    }
    assert surface_metadata["dateTime"].isel(Location=0).values == np.datetime64(
        "2026-09-30T18:00:00", "ns"
    )
    assert surface_metadata["stationIdentification"].isel(Location=0).item() == "72365"
    assert surface_metadata["pressure"].isel(Location=0).item() == pytest.approx(
        98340.0
    )
    assert surface_metadata["stationIdentification"].isel(Location=1).item() == "72451"
    assert surface_metadata["pressure"].isel(Location=1).item() == pytest.approx(
        99150.0
    )
    assert metadata["latitude"].attrs["units"] == "degrees_north"
    assert metadata["longitude"].attrs["units"] == "degrees_east"
    assert metadata["latitude"].isel(Location=0).item() == pytest.approx(35.04)
    assert metadata["longitude"].isel(Location=0).item() == pytest.approx(-106.62)
    assert metadata["latitude"].isel(Location=12).item() == pytest.approx(37.76)
    assert metadata["longitude"].isel(Location=12).item() == pytest.approx(-99.97)
    assert surface_metadata["estimatedLatitude"].isel(
        Location=0
    ).item() == pytest.approx(35.04)
    assert surface_metadata["estimatedLongitude"].isel(
        Location=0
    ).item() == pytest.approx(-106.62)
    assert metadata["estimatedLatitude"].isel(Location=3).item() > 35.04
    assert metadata["estimatedLongitude"].isel(Location=3).item() > -106.62
    assert np.isnan(metadata["estimatedLatitude"].isel(Location=11).item())
    assert np.isnan(metadata["estimatedLongitude"].isel(Location=11).item())
    assert metadata["pressure"].attrs["units"] == "Pa"
    assert metadata["height"].isel(Location=3).item() == pytest.approx(3068.0)
    assert observations["temperature"].isel(Location=3).item() == pytest.approx(276.75)
    assert observations["dewPointTemperature"].isel(Location=3).item() == pytest.approx(
        273.35
    )
    assert observations["windEastward"].attrs["units"] == "m s-1"
    assert observations["windNorthward"].attrs["units"] == "m s-1"
    assert observations["windEastward"].isel(Location=3).item() == pytest.approx(
        -(13 * 0.514444) * np.sin(np.deg2rad(230.0))
    )
    assert observations["windNorthward"].isel(Location=3).item() == pytest.approx(
        -(13 * 0.514444) * np.cos(np.deg2rad(230.0))
    )
    assert metadata["pressure"].isel(Location=11).item() == pytest.approx(23300.0)
    assert np.isnan(metadata["height"].isel(Location=11).item())
    assert np.isnan(observations["temperature"].isel(Location=11).item())
    assert observations["windEastward"].isel(Location=11).item() == pytest.approx(
        -(72 * 0.514444) * np.sin(np.deg2rad(215.0))
    )
    assert observations["windNorthward"].isel(Location=11).item() == pytest.approx(
        -(72 * 0.514444) * np.cos(np.deg2rad(215.0))
    )


def test_temp_drift_estimate_uses_five_meter_per_second_ascent():
    """Verify layer wind drift uses the configured vertical ascent rate.

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
    observation = _Observation(
        pressure=100000.0,
        height=110.0,
        temperature=None,
        dew_point_temperature=None,
        wind_direction=270.0,
        wind_speed=10.0,
        raw_code="70000",
    )

    estimated_latitudes, estimated_longitudes = _estimate_drift_positions(
        [observation], 0.0, 0.0, 100.0
    )

    assert estimated_latitudes[0] == pytest.approx(0.0)
    assert estimated_longitudes[0] == pytest.approx(np.rad2deg(20.0 / 6_371_000.0))


def test_temp_parser_leaves_unlisted_station_coordinates_missing():
    """Verify stations absent from the location table have missing coordinates.

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
    report_text = "TTAA 30181 99999 99900 12558 19513 31313="

    data_trees = TempParser().parse(report_text, REFERENCE_DATETIME)
    metadata = data_trees["surface"]["MetaData"].dataset

    assert np.isnan(metadata["latitude"].values).all()
    assert np.isnan(metadata["longitude"].values).all()


def test_temp_parser_decodes_valid_tropopause_as_an_observation():
    """Verify valid tropopause data uses the normal observation variables.

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
    report_text = "TTAA 30181 72365 88950 12558 19513 77233 21572 31313="

    data_trees = TempParser().parse(report_text, REFERENCE_DATETIME)
    assert set(data_trees) == {"upper_air"}
    metadata = data_trees["upper_air"]["MetaData"].dataset
    observations = data_trees["upper_air"]["ObsValue"].dataset

    assert data_trees["upper_air"].attrs["observation_count"] == 2
    assert metadata["pressure"].values.tolist() == pytest.approx([95000.0, 23300.0])
    assert np.isnan(metadata["height"].values).all()
    assert observations["temperature"].isel(Location=0).item() == pytest.approx(285.65)
    assert observations["dewPointTemperature"].isel(Location=0).item() == pytest.approx(
        277.65
    )
    assert observations["windEastward"].isel(Location=0).item() == pytest.approx(
        -(13 * 0.514444) * np.sin(np.deg2rad(195.0))
    )
    assert observations["windNorthward"].isel(Location=0).item() == pytest.approx(
        -(13 * 0.514444) * np.cos(np.deg2rad(195.0))
    )
    assert np.isnan(observations["temperature"].isel(Location=1).item())
    assert observations["windEastward"].isel(Location=1).item() == pytest.approx(
        -(72 * 0.514444) * np.sin(np.deg2rad(215.0))
    )
    assert observations["windNorthward"].isel(Location=1).item() == pytest.approx(
        -(72 * 0.514444) * np.cos(np.deg2rad(215.0))
    )


def test_temp_parser_includes_combined_raw_code_on_request():
    """Verify raw code groups are optional and combined per observation.

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
    data_trees = TempParser().parse(
        TEMP_REPORT, REFERENCE_DATETIME, include_raw_code=True
    )
    surface_metadata = data_trees["surface"]["MetaData"].dataset
    metadata = data_trees["upper_air"]["MetaData"].dataset

    assert "rawCode" in metadata
    assert metadata["rawCode"].dims == ("Location",)
    assert surface_metadata["rawCode"].isel(Location=0).item() == "99834 17256 22507"
    assert metadata["rawCode"].isel(Location=3).item() == "70068 03634 23013"
    assert metadata["rawCode"].isel(Location=11).item() == "77233 21572"


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
    direction, speed = TempParser._decode_wind_group("00000", "08180")

    assert direction is None
    assert speed == 0.0


def test_temp_parser_resolves_datetime_across_year_boundary():
    """Verify day/hour resolves against a reference month and year.

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
    reference_datetime = datetime(2025, 1, 1, 12, tzinfo=UTC)

    observation_datetime = TempParser._resolve_datetime("81180", reference_datetime)

    assert observation_datetime == datetime(2024, 12, 31, 18, tzinfo=UTC)


def test_temp_parser_rejects_invalid_datetime_inputs():
    """Verify TEMP date resolution requires a valid UTC reference and day.

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
    with pytest.raises(ValueError, match="reference_datetime is required"):
        TempParser().parse(TEMP_REPORT)

    with pytest.raises(ValueError, match="timezone-aware"):
        naive_datetime = REFERENCE_DATETIME.replace(tzinfo=None)
        TempParser().parse(TEMP_REPORT, naive_datetime)

    with pytest.raises(ValueError, match="Invalid TEMP day/hour"):
        TempParser._resolve_datetime("82181", REFERENCE_DATETIME)


def test_temp_day_plus_fifty_marks_knots():
    """Verify the TEMP day +50 convention also selects knots.

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
    direction, speed = TempParser._decode_wind_group("23013", "80180")

    assert direction == 230.0
    assert speed == pytest.approx(13 * 0.514444)


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

    data_trees = TempIngestor(REFERENCE_DATETIME, include_raw_code=True)._process(
        str(report_path)
    )
    upper_air_tree = data_trees["upper_air"]
    assert (
        upper_air_tree["MetaData"]
        .dataset["stationIdentification"]
        .isel(Location=0)
        .item()
        == "72365"
    )
    assert "rawCode" in upper_air_tree["MetaData"].dataset
