from datetime import UTC, datetime
from pathlib import Path

import numpy as np
import pytest

from geode.data.data_manager import data_manager
from geode.ingest.consumers import tac_gts_reader
from geode.ingest.ingestors.tac_gts import TempIngestor
from geode.ingest.ingestors.tac_ingestor import TacIngestor
from geode.utils.tac.temp_parser import (
    TempParser,
    _estimate_drift_positions,
    _Observation,
)

TEMP_REPORT = """375
USUS01 KWBC 061200 RRB
TTAA 56121 72403 99013 08642 30503 00195 10258 34010 92839 06869
01021 85530 06078 31519 70125 04079 28530 50579 10762 29035 40746
23374 28048 30950 38366 28054 25073 46766 27555 20218 54564 27558
15399 62367 27066 10646 67569 28050 88105 67767 27049 77159 26573
41314 31313 44108 81106=
TTAA 56121 72440 99974 13249 16505 00165 ///// ///// 92829 17861
19010 85545 12458 27508 70167 09079 28008 50585 11962 29515 40752
23563 30521 30956 38363 29517 25079 45362 28033 20225 53761 26541
15407 59161 27047 10656 66560 27532 88104 66360 28029 77999 31313
45408 81118 51515 10164 00006 10194 26007 24507=

376
UKUS01 KWBC 061200 RRD
TTBB 56128 72403 00013 08642 11004 10458 22963 08458 33935 06861
44924 07071 55918 06672 66897 05464 77890 05273 88883 04660 99881
04660 11869 05870 22861 05468 33860 05269 44854 05679 55841 06282
66838 07298 77830 06699 88819 08499 99806 09499 11775 09099 22732
06299 33697 03879 44670 03087 55666 02877 66656 01667 77647 00665
88640 00065 99632 00370 11622 01565 22618 01966 33615 02168 44609
02185 55603 02580 66601 02968 77590 03581 88582 04176 99577 04565
11569 04969 22564 05163 33557 05762 44542 06761 55530 07363 66481
13362 77474 14165 88453 16767 99436 19167 11428 20367 22417 21568
33416 21768 44414 22168 55410 22376 66357 28572 77353 29367 88344
30766 99322 34370 11285 41363 22272 43762 33265 44764 44264 44566
55253 46167 66229 50961 77228 51163 88225 50369 99221 49969 11196
55564 22185 57365 33178 59564 44173 59765 55172 59566 66151 62367
77145 61969 88133 63769 99129 62971 11118 64172 22105 67767 33100
67569 21212 00013 30503 11999 34510 22935 01518 33919 00522 44854
31518 55823 32020 66759 29025 77574 28532 88539 29535 99159 26573
11100 28050 31313 44108 81106 41414 00900 51515 10164 00091 10194
35517 30022=
TTBB 56128 72440 00974 13249 11953 18460 22939 18261 33932 18061
44925 17861 55919 17862 66836 11058 77829 10458 88792 13286 99781
13482 11758 12677 22734 11278 33720 10679 44648 05481 55517 09962
66510 10761 77492 12363 88479 13963 99473 14363 11460 15364 22442
17963 33433 18963 44421 20562 55413 21565 66402 23362 77391 24766
88366 28964 99364 29564 11341 33759 22333 34161 33321 34764 44295
39363 55293 39763 66282 41163 77277 40963 88270 41564 99218 52558
11216 52958 22211 52759 33188 54961 44180 55961 55166 56962 66163
57361 77159 57962 88133 62361 99130 62761 11127 63360 22124 63960
33121 63961 44115 64560 55105 66160 66104 66360 77103 66560 88100
66560 21212 00974 16505 11964 16519 22956 16019 33950 16518 44917
19508 55905 23006 66893 26509 77886 27508 88873 28007 99863 29009
11844 27509 22835 29009 33824 28508 44806 23011 55796 20510 66789
19511 77780 20512 88771 21508 99763 20508 11747 25005 22740 28506
33726 27509 44720 27510 55706 29007 66699 28008 77687 26507 88678
27506 99657 28515 11651 28514 22628 30517 33617 30515 44594 30018
55582 30516 66572 30511 77566 30511 88561 30511 99551 30513 11546
30511 22541 30512 33531 30013 44521 30512 55506 29514 66495 29517
77490 30018 88475 31016 99461 29519 11452 29516 22443 30518 33438
30518 44429 30520 55417 30021 66408 30521 77404 30520 88396 30523
99384 32024 11380 32024 22372 32022 33368 31523 44360 32024 55337
32023 66333 31519 77326 30521 88315 29517 99312 29516 11308 29516
22302 29518 33295 29518 44281 30521 55271 28030 66258 27535 77255
27534 88239 28530 99227 28034 11221 27531 22210 27045 33207 27544
44199 26541 55187 27047 66180 26547 77175 27050 88168 27545 99162
27049 11159 27050 22155 26545 33151 27047 44145 27046 55141 27052
66137 27549 77132 28044 88130 27546 99124 28042 11121 28545 22112
29036 33105 28029 44103 27530 55100 27532 31313 45408 81118 41414
10908 51515 10164 00006 10194 26007 24507=

TTCC 56121 72403 70864 63375 26030 50072 59778 23019 30396 52582
29017 20659 51383 26509 10112 45987 26520 88999 77999 31313 44108
81106=

383
UEUS01 KWBC 061200 RRB
TTDD 5612/ 72403 11974 67969 22941 66571 33929 64373 44813 64973
55724 62775 66651 64374 77549 59978 88517 61777 99506 59378 11476
60777 22448 58179 33428 58579 44401 54781 55347 57179 66315 54781
77302 52182 88283 53981 99257 52582 11239 49584 22212 51982 33199
51183 44193 52782 55184 52782 66155 49984 77136 51583 88131 48585
99117 47186 11108 48385 22094 44787 33086 45787 44076 42788 21212
11919 29041 22793 27037 33759 29031 44723 28026 55698 26031 66596
31030 77584 32025 88547 27513 99530 28014 11506 23017 22481 25027
33444 30019 44423 31014 55408 29019 66394 30018 77381 25514 88373
26013 99346 25513 11318 28526 22313 29522 33290 29513 44285 28010
55282 26512 66264 30526 77251 30515 88243 33019 99237 32012 11229
27511 22208 32004 33185 25510 44182 27515 55176 24014 66154 27521
77148 26525 88141 30017 99136 28020 11131 29015 22128 28510 33125
24510 44119 23014 55114 26514 66110 24509 77109 23011 88104 25520
99093 28025 11090 27029 22083 26516 33076 28020 31313 44108
81106=
"""
REFERENCE_DATETIME = datetime(2026, 10, 6, 12, tzinfo=UTC)


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
    surface_remarks = surface_tree["Remarks"].dataset
    metadata = upper_air_tree["MetaData"].dataset
    observations = upper_air_tree["ObsValue"].dataset
    remarks = upper_air_tree["Remarks"].dataset
    assert surface_tree.attrs["observation_count"] == 2
    assert upper_air_tree.attrs["observation_count"] == 326
    assert "assumed_ascent_rate_m_s" not in surface_tree.attrs
    assert "assumed_ascent_rate_m_s" not in upper_air_tree.attrs
    assert "position_estimation_method" not in surface_tree.attrs
    assert "position_estimation_method" not in upper_air_tree.attrs
    assert surface_metadata.sizes["Location"] == 2
    assert surface_observations.sizes["Location"] == 2
    assert surface_remarks.sizes["Location"] == 2
    assert metadata.sizes["Location"] == 326
    assert observations.sizes["Location"] == 326
    assert remarks.sizes["Location"] == 326
    assert set(metadata.data_vars) == {
        "dateTime",
        "receiptTime",
        "stationIdentification",
        "latitude",
        "longitude",
        "pressure",
        "height",
        "reportType",
    }
    assert set(surface_metadata.data_vars) == {
        "dateTime",
        "receiptTime",
        "stationIdentification",
        "latitude",
        "longitude",
        "height",
        "reportType",
    }
    assert all(
        variable.dims == ("Location",) for variable in metadata.data_vars.values()
    )
    assert all(
        variable.dims == ("Location",) for variable in observations.data_vars.values()
    )
    assert set(surface_observations.data_vars) == {
        "stationPressure",
        "temperature",
        "dewPointTemperature",
        "windEastward",
        "windNorthward",
    }
    assert set(observations.data_vars) == {
        "temperature",
        "dewPointTemperature",
        "windEastward",
        "windNorthward",
    }
    assert set(surface_metadata["reportType"].values) == {"TTAA"}
    assert set(metadata["reportType"].values) == {"TTAA", "TTBB", "TTCC", "TTDD"}
    assert {
        section_code: int((metadata["reportType"].values == section_code).sum())
        for section_code in ("TTAA", "TTBB", "TTCC", "TTDD")
    } == {"TTAA": 25, "TTBB": 221, "TTCC": 5, "TTDD": 75}
    assert surface_metadata["dateTime"].isel(Location=0).values == np.datetime64(
        "2026-10-06T12:00:00", "ns"
    )
    assert surface_metadata["stationIdentification"].isel(Location=0).item() == "72403"
    assert surface_observations["stationPressure"].isel(
        Location=0
    ).item() == pytest.approx(101300.0)
    assert surface_metadata["stationIdentification"].isel(Location=1).item() == "72440"
    assert metadata["latitude"].attrs["units"] == "degrees_north"
    assert metadata["longitude"].attrs["units"] == "degrees_east"
    assert "comment" not in metadata["latitude"].attrs
    assert "comment" not in metadata["longitude"].attrs
    assert set(surface_remarks.data_vars) == {"position", "source"}
    assert set(remarks.data_vars) == {"position", "source"}
    assert surface_remarks["position"].dims == ("Location",)
    assert remarks["position"].dims == ("Location",)
    assert surface_remarks["source"].dims == ("Location",)
    assert remarks["source"].dims == ("Location",)
    position_remark = (
        "Estimated through trapezoidal integration of layer winds, "
        "assuming 5m/s ascent rate."
    )
    source_remark = "Decoded from raw WMO TEMP TAC groups by GEODE."
    np.testing.assert_array_equal(
        surface_remarks["position"].values, [position_remark] * 2
    )
    np.testing.assert_array_equal(remarks["position"].values, [position_remark] * 326)
    np.testing.assert_array_equal(surface_remarks["source"].values, [source_remark] * 2)
    np.testing.assert_array_equal(remarks["source"].values, [source_remark] * 326)
    assert surface_metadata["latitude"].isel(Location=0).item() == pytest.approx(38.98)
    assert surface_metadata["longitude"].isel(Location=0).item() == pytest.approx(
        -77.49
    )
    assert metadata["pressure"].attrs["units"] == "Pa"
    assert surface_observations["stationPressure"].attrs["units"] == "Pa"
    assert observations["windEastward"].attrs["units"] == "m s-1"
    assert observations["windNorthward"].attrs["units"] == "m s-1"

    ttaa_indices = np.flatnonzero(metadata["reportType"].values == "TTAA")
    ttbb_indices = np.flatnonzero(metadata["reportType"].values == "TTBB")
    ttcc_indices = np.flatnonzero(metadata["reportType"].values == "TTCC")
    ttdd_indices = np.flatnonzero(metadata["reportType"].values == "TTDD")
    ttaa_700_hpa = ttaa_indices[metadata["pressure"].values[ttaa_indices] == 70000.0][0]
    assert metadata["height"].isel(Location=ttaa_700_hpa).item() == pytest.approx(
        3125.0
    )
    assert observations["temperature"].isel(
        Location=ttaa_700_hpa
    ).item() == pytest.approx(277.15)
    assert metadata["pressure"].isel(Location=ttbb_indices[0]).item() == pytest.approx(
        101300.0
    )
    assert observations["temperature"].isel(
        Location=ttbb_indices[0]
    ).item() == pytest.approx(281.75)
    assert metadata["pressure"].isel(Location=ttcc_indices[0]).item() == pytest.approx(
        7000.0
    )
    assert observations["temperature"].isel(
        Location=ttcc_indices[0]
    ).item() == pytest.approx(259.85)
    assert metadata["pressure"].isel(Location=ttdd_indices[0]).item() == pytest.approx(
        9740.0
    )
    assert observations["temperature"].isel(
        Location=ttdd_indices[0]
    ).item() == pytest.approx(255.25)
    assert np.isfinite(observations["windEastward"].values[ttdd_indices]).any()


def test_temp_parser_skips_fully_missing_mandatory_level():
    """Verify a below-ground mandatory level with no values is omitted.

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
    report_text = "TTAA 56121 72403 00/// ///// ///// 92839 06869 01021 31313="
    data_trees = TempParser().parse(
        report_text, REFERENCE_DATETIME, include_raw_code=True
    )
    raw_codes = data_trees["upper_air"]["MetaData"].dataset["rawCode"].values

    assert "00/// ///// /////" not in raw_codes


def test_temp_ingestor_stores_and_reads_icechunk(tmp_path, use_empty_data_lake):
    """Verify TEMP reports are persisted to Icechunk and can be read back.

    Parameters
    ----------
    tmp_path : pathlib.Path
        Temporary directory for the TAC report fixture.
    use_empty_data_lake : None
        Fixture that prepares and cleans the configured data lake.

    Returns
    -------
    None

    Examples
    --------
    Run with ``pytest test/test_tac_gts_reader.py``.
    """
    report_path = tmp_path / "temp.tac"
    report_path.write_text(TEMP_REPORT, encoding="ascii")

    TempIngestor(reference_datetime=REFERENCE_DATETIME).process(str(report_path))

    surface_path = data_manager.get_file_path("temp_surface")
    upper_air_path = data_manager.get_file_path("temp_upper_air")
    assert Path(surface_path).is_dir()
    assert Path(upper_air_path).is_dir()

    start_datetime = datetime(2026, 10, 6, tzinfo=UTC)
    end_datetime = datetime(2026, 10, 7, tzinfo=UTC)
    surface_tree = data_manager.get("temp_surface", start_datetime, end_datetime)
    upper_air_tree = data_manager.get("temp_upper_air", start_datetime, end_datetime)

    assert surface_tree["MetaData"].dataset.sizes["Location"] == 2
    assert upper_air_tree["MetaData"].dataset.sizes["Location"] == 326
    assert (
        surface_tree["MetaData"]
        .dataset["stationIdentification"]
        .isel(Location=0)
        .item()
        == "72403"
    )
    assert np.isfinite(
        upper_air_tree["ObsValue"].dataset["temperature"].isel(Location=3).item()
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
    assert surface_metadata["rawCode"].isel(Location=0).item() == "99013 08642 30503"
    assert metadata["rawCode"].isel(Location=3).item() == "70125 04079 28530"
    assert "70864 63375 26030" in metadata["rawCode"].values
    assert "11974 67969" in metadata["rawCode"].values


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


@pytest.mark.parametrize(
    ("direction_group", "speed_group", "expected_direction", "expected_speed"),
    [
        pytest.param("00000", "08180", None, 0.0, id="calm-wind"),
        pytest.param("23013", "80180", 230.0, 13 * 0.514444, id="knots"),
    ],
)
def test_temp_parser_decodes_wind_groups(
    direction_group, speed_group, expected_direction, expected_speed
):
    """Verify TEMP wind groups decode calm and knots-coded winds.

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
    direction, speed = TempParser._decode_wind_group(direction_group, speed_group)

    assert direction == expected_direction
    assert speed == pytest.approx(expected_speed)


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
        == "72403"
    )
    assert "rawCode" in upper_air_tree["MetaData"].dataset
