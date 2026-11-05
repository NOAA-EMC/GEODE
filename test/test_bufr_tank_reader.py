import datetime
import os

import pytest

from geode.configs.geode_config import geode_config
from geode.ingest.consumers import bufr_tank_reader

Day1 = datetime.datetime(2024, 1, 1, tzinfo=datetime.UTC)
Day2 = datetime.datetime(2024, 1, 2, tzinfo=datetime.UTC)
Day3 = datetime.datetime(2024, 1, 3, tzinfo=datetime.UTC)


@pytest.fixture()
def tank_root(tmp_path, monkeypatch):
    monkeypatch.setattr(geode_config.bufr_tank, "root_path", str(tmp_path))
    monkeypatch.setattr(geode_config.bufr_tank, "include_restricted", False)
    monkeypatch.setattr(geode_config.bufr_tank, "allow_unmapped", False)
    return tmp_path


def _touch_tank(root, day: datetime.datetime, tank_id: str) -> str:
    path = os.path.join(root, day.strftime("%Y%m%d"), tank_id)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    open(path, "wb").close()
    return path


@pytest.mark.parametrize(
    ("tank_id", "dataset"),
    [
        ("b000/xx001", "surface_synop"),
        ("b000/xx002", "surface_synop"),
        ("b000/xx007", "surface_metar"),
    ],
)
def test_ingest_returns_dataset_name(tank_root, tank_id, dataset):
    _touch_tank(tank_root, Day1, tank_id)

    reader = bufr_tank_reader.BufrTankReader()
    assert reader.ingest(tank_id, Day1, Day1) == dataset


def test_get_file_paths_skips_missing_days(tank_root):
    path1 = _touch_tank(tank_root, Day1, "b000/xx001")
    path3 = _touch_tank(tank_root, Day3, "b000/xx001")

    reader = bufr_tank_reader.BufrTankReader()
    assert reader.get_file_paths("b000/xx001", Day1, Day3) == [path1, path3]


def test_restricted_tank_requires_opt_in(tank_root, monkeypatch):
    reader = bufr_tank_reader.BufrTankReader()
    with pytest.raises(PermissionError, match="restricted"):
        reader.ingest("b000/xx000", Day1, Day2)

    monkeypatch.setattr(geode_config.bufr_tank, "include_restricted", True)
    assert reader.ingest("b000/xx000", Day1, Day2) == "surface_synop_restricted"


def test_unknown_or_malformed_tank_raises(tank_root):
    reader = bufr_tank_reader.BufrTankReader()
    with pytest.raises(KeyError):
        reader.ingest("b000/xx999", Day1, Day1)
    with pytest.raises(ValueError):
        reader.ingest("surface_synop", Day1, Day1)


def test_unmapped_tank_error_suggests_opt_in(tank_root):
    from geode.configs.table_a_mapping import UnmappedBufrTankError

    reader = bufr_tank_reader.BufrTankReader()
    with pytest.raises(UnmappedBufrTankError, match="bufr_tank.allow_unmapped: true"):
        reader.ingest("b000/xx999", Day1, Day1)


def test_allow_unmapped_falls_back_to_tank_name(tank_root, monkeypatch, caplog):
    monkeypatch.setattr(geode_config.bufr_tank, "allow_unmapped", True)
    path = _touch_tank(tank_root, Day1, "b000/xx999")

    reader = bufr_tank_reader.BufrTankReader()
    info = reader.get_bufr_tank_info("b000/xx999")
    assert info.dataset == "b000_xx999"
    assert info.category_name == "unmapped"
    assert reader.get_file_paths(info.tank_id, Day1, Day1) == [path]

    with caplog.at_level("WARNING", logger=bufr_tank_reader.__name__):
        assert reader.ingest("b000/xx999", Day1, Day1) == "b000_xx999"
    assert "fallback dataset name 'b000_xx999'" in caplog.text


def test_allow_unmapped_keeps_mapped_names(tank_root, monkeypatch):
    monkeypatch.setattr(geode_config.bufr_tank, "allow_unmapped", True)

    reader = bufr_tank_reader.BufrTankReader()
    assert reader.ingest("b000/xx001", Day1, Day1) == "surface_synop"


def test_allow_unmapped_still_rejects_malformed_ids(tank_root, monkeypatch):
    monkeypatch.setattr(geode_config.bufr_tank, "allow_unmapped", True)

    reader = bufr_tank_reader.BufrTankReader()
    with pytest.raises(ValueError, match="bAAA/xxBBB"):
        reader.ingest("b000/xx01", Day1, Day1)


def test_prefers_tank_specific_ingestor(tank_root, monkeypatch):
    from geode.ingest.ingestors import factory

    calls = []

    class _Recorder:
        def __init__(self, label):
            self.label = label

        def __call__(self, info):
            recorder = self

            class _Ingestor:
                def process(self, file_path):
                    calls.append((recorder.label, info.dataset, file_path))

            return _Ingestor()

    monkeypatch.setitem(
        factory.RegisteredIngestors, "bufr_tank/surface_synop", _Recorder("dataset")
    )
    monkeypatch.setitem(
        factory.RegisteredIngestors, "bufr_tank/b000/xx002", _Recorder("tank")
    )
    monkeypatch.setattr(bufr_tank_reader.BufrTankReader, "_init_mpi", lambda self: None)

    path1 = _touch_tank(tank_root, Day1, "b000/xx001")
    path2 = _touch_tank(tank_root, Day1, "b000/xx002")

    reader = bufr_tank_reader.BufrTankReader()
    reader.ingest("b000/xx001", Day1, Day1)
    reader.ingest("b000/xx002", Day1, Day1)

    assert calls == [
        ("dataset", "surface_synop", path1),
        ("tank", "surface_synop", path2),
    ]


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-v"]))
