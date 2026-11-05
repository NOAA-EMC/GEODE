import pytest

from geode.configs.table_a_mapping import (
    UnmappedBufrTankError,
    format_bufr_tank_id,
    parse_bufr_tank_id,
    table_a_mapping,
    unmapped_bufr_tank_info,
)


@pytest.mark.parametrize(
    ("tank_id", "expected"),
    [
        ("b000/xx001", (0, 1)),
        ("b021/xx041", (21, 41)),
        ("b255/xx255", (255, 255)),
        ("/b000/xx001/", (0, 1)),
    ],
)
def test_parse_bufr_tank_id(tank_id, expected):
    assert parse_bufr_tank_id(tank_id) == expected


@pytest.mark.parametrize(
    "tank_id", ["b0/xx1", "000/001", "b000xx001", "b000/xx0001", "", "surface_synop"]
)
def test_parse_bufr_tank_id_rejects_malformed(tank_id):
    with pytest.raises(ValueError, match="bAAA/xxBBB"):
        parse_bufr_tank_id(tank_id)


def test_format_bufr_tank_id_zero_pads():
    assert format_bufr_tank_id(0, 1) == "b000/xx001"
    assert format_bufr_tank_id(21, 41) == "b021/xx041"


@pytest.mark.parametrize(
    ("tank_id", "dataset"),
    [
        ("b000/xx001", "surface_synop"),
        ("b000/xx002", "surface_synop"),
        ("b000/xx007", "surface_metar"),
        ("b000/xx000", "surface_synop_restricted"),
    ],
)
def test_get_dataset(tank_id, dataset):
    assert table_a_mapping.get_dataset(tank_id) == dataset


def test_get_returns_full_entry():
    info = table_a_mapping.get("b000/xx002")
    assert info.category == 0
    assert info.subtype == 2
    assert info.category_name == "surface land"
    assert info.format == "WMO FM-14 SYNOP MOBIL"
    assert info.restricted is False
    assert info.tank_id == "b000/xx002"


def test_unknown_bufr_tank_raises():
    with pytest.raises(UnmappedBufrTankError, match="b000/xx999") as error:
        table_a_mapping.get("b000/xx999")
    assert isinstance(error.value, KeyError)
    assert str(error.value).startswith("BUFR tank 'b000/xx999'")


def test_unmapped_bufr_tank_info():
    info = unmapped_bufr_tank_info("b031/xx200")
    assert info.dataset == "b031_xx200"
    assert info.tank_id == "b031/xx200"
    assert (info.category, info.subtype) == (31, 200)
    assert info.category_name == "unmapped"
    assert info.format == "unknown"


def test_contains_and_bufr_tank_ids_round_trip():
    assert "b000/xx001" in table_a_mapping
    assert "b000/xx999" not in table_a_mapping
    assert "not-a-tank" not in table_a_mapping

    tank_ids = table_a_mapping.bufr_tank_ids()
    assert tank_ids == sorted(tank_ids)
    assert all(table_a_mapping.get(t).tank_id == t for t in tank_ids)


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-v"]))
