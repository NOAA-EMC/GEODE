import numpy as np
import pytest
import xarray as xr

from geode.ingest.generic_bufr.normalize import normalize_dataset, rectangularize_field
from geode.ingest.generic_bufr.schema import (
    SchemaMismatchError,
    build_mapping,
    check_schema_hash,
    discover_schema,
    sanitize_name,
)
from geode.ingest.generic_bufr.tables import (
    BufrTableError,
    parse_dx_table,
    parse_sequence_items,
)

TABLE = """
| MNEMONIC | NUMBER | DESCRIPTION |
| NC999001 | A48102 | Test subset |
| MNEMONIC | NUMBER | DESCRIPTION |
| NC999001 | 3-40-001 | Subset sequence |
| NC999001 | HDR  {LEVL} "CHNL"3 |
| HDR      | 3-01-001 | Header |
| HDR      | YEAR MNTH DAYS HOUR MINU CLATH |
| LEVL     | 3-01-002 | Level |
| LEVL     | PRLC TMDB |
| CHNL     | 3-01-003 | Channel |
| CHNL     | TMBR PRLC |
| MNEMONIC | NUMBER | SCAL | REFERENCE | BIT | UNITS | DESCRIPTION |
| YEAR  | 0-00-000 | 0 | 0 | 12 | YEAR | Year |
| MNTH  | 0-00-000 | 0 | 0 | 4 | MONTH | Month |
| DAYS  | 0-00-000 | 0 | 0 | 6 | DAY | Day |
| HOUR  | 0-00-000 | 0 | 0 | 5 | HOUR | Hour |
| MINU  | 0-00-000 | 0 | 0 | 6 | MINUTE | Minute |
| CLATH | 0-00-000 | 5 | -9000000 | 25 | DEGREES | Latitude |
| PRLC  | 0-00-000 | -1 | 0 | 14 | PA | Pressure |
| TMDB  | 0-00-000 | 1 | 0 | 12 | K | Temperature |
| TMBR  | 0-00-000 | 2 | 0 | 16 | K | Brightness temperature |
"""


def _schema():
    return discover_schema(parse_dx_table(TABLE))


def test_parse_sequence_items_replication_kinds():
    items = parse_sequence_items('A {B} (C) <D> [E] "F"4')
    assert [(i.mnemonic, i.replication, i.count) for i in items] == [
        ("A", None, None),
        ("B", "delayed", None),
        ("C", "delayed", None),
        ("D", "delayed", None),
        ("E", "delayed", None),
        ("F", "fixed", 4),
    ]


def test_parse_dx_table_rejects_empty():
    with pytest.raises(BufrTableError):
        parse_dx_table("no table here")


def test_unknown_mnemonic_fails_loudly():
    bad = TABLE.replace("PRLC TMDB", "PRLC NOPE")
    with pytest.raises(BufrTableError, match="NOPE"):
        discover_schema(parse_dx_table(bad))


def test_discovery_is_deterministic():
    first = _schema()
    second = discover_schema(parse_dx_table(TABLE))
    assert [f.name for f in first.fields] == [f.name for f in second.fields]
    assert first.schema_hash == second.schema_hash
    keys = [(f.group, f.path, f.mnemonic) for f in first.fields]
    assert keys == sorted(keys)


def test_schema_hash_changes_with_units():
    changed = discover_schema(parse_dx_table(TABLE.replace("| K | Temp", "| C | Temp")))
    assert changed.schema_hash != _schema().schema_hash


def test_replication_dimensions():
    schema = _schema()
    by_name = {(f.group, f.name): f for f in schema.fields}
    assert by_name[("LEVL", "TMDB")].dimensions == ("Location", "LEVL")
    assert by_name[("CHNL", "TMBR")].dimensions == ("Location", "CHNL")
    assert schema.dimension_sizes == {"CHNL": 3, "LEVL": None}


def test_name_collisions_are_path_qualified():
    schema = _schema()
    names = [(f.group, f.name) for f in schema.fields]
    assert len(names) == len(set(names))
    prlc = [f for f in schema.fields if f.mnemonic == "PRLC"]
    assert {f.group for f in prlc} == {"LEVL", "CHNL"}

    collide = TABLE.replace(
        "| NC999001 | HDR  {LEVL}", "| NC999001 | INNR {LEVL}"
    ).replace(
        "| HDR      | 3-01-001 | Header |",
        "| INNR     | 3-01-009 | Inner |\n| INNR | PRLC {PRLC} |\n| HDR | 3-01-001 | Header |",
    )
    fields = [
        f
        for f in discover_schema(parse_dx_table(collide)).fields
        if f.mnemonic == "PRLC"
    ]
    names = [(f.group, f.name) for f in fields]
    assert len(names) == len(set(names))


def test_sanitize_name():
    assert sanitize_name("A-B.C") == "A_B_C"
    assert sanitize_name("1AB") == "_1AB"


def test_ambiguous_subset_requires_choice():
    two = TABLE.replace(
        "| NC999001 | A48102 | Test subset |",
        "| NC999001 | A48102 | Test subset |\n| NC999002 | A48103 | Other |",
    )
    with pytest.raises(BufrTableError, match="Specify a subset"):
        discover_schema(parse_dx_table(two))


def test_build_mapping_has_provenance_and_datetime():
    mapping = build_mapping(_schema())
    names = [v["name"] for v in mapping["encoder"]["variables"]]
    assert names[0] == "MetaData/dateTime"
    tmbr = next(v for v in mapping["encoder"]["variables"] if v["name"] == "CHNL/TMBR")
    assert tmbr["units"] == "K"
    assert tmbr["dimensions"] == ["Location", "CHNL"]
    assert tmbr["path"] == "*/CHNL/TMBR"
    lat = next(
        v for v in mapping["encoder"]["variables"] if v["name"] == "HDR/CLATH"
    )
    assert "dimensions" not in lat


def test_rectangularize_ragged():
    values, counts = rectangularize_field([[1.0, 2.0], [3.0], []])
    assert values.shape == (3, 2)
    assert counts.tolist() == [2, 1, 0]
    assert np.isnan(values[1, 1]) and np.isnan(values[2, 0])
    padded, _ = rectangularize_field([[1.0]], length=4)
    assert padded.shape == (1, 4)
    with pytest.raises(ValueError):
        rectangularize_field([[1.0, 2.0, 3.0]], length=2)


def test_normalize_dataset_pads_and_sorts():
    ds = xr.Dataset(
        {"b": (("Location", "LEVL"), np.ones((2, 2))), "a": (("Location",), [1, 2])}
    )
    out = normalize_dataset(ds, {}, max_replication_length=4)
    assert out.sizes["LEVL"] == 4
    assert list(out.data_vars) == ["a", "b"]
    with pytest.raises(ValueError):
        normalize_dataset(ds, {}, max_replication_length=1)
    with pytest.raises(ValueError):
        normalize_dataset(ds, {"LEVL": 3})


def test_schema_hash_policy():
    assert check_schema_hash(None, "x")
    assert check_schema_hash("x", "x")
    assert not check_schema_hash("y", "x")
    assert issubclass(SchemaMismatchError, RuntimeError)


def test_registry_and_curated_ingestors_intact():
    pytest.importorskip("bufr")
    from geode.ingest import ingestors

    registered = set(ingestors.directory())
    curated = {
        f"ncep_dump/{n}" for n in ("atms", "mhs", "iasi", "cris", "radiosonde", "amsua")
    }
    assert curated | {"ncep_dump/generic_bufr"} <= registered


def test_generic_ingestor_policy_validation():
    pytest.importorskip("bufr")
    from geode.ingest.ingestors.generic_bufr import GenericBufrIngestor

    with pytest.raises(ValueError):
        GenericBufrIngestor(on_schema_mismatch="bogus")
    with pytest.raises(FileNotFoundError):
        GenericBufrIngestor().discover("/nonexistent.bufr")


def test_generic_ingestor_integration_with_dump(use_dump, tmp_path):
    pytest.importorskip("bufr")
    import glob
    import shutil

    from geode.configs.geode_config import geode_config
    from geode.ingest.ingestors.generic_bufr import GenericBufrIngestor

    if shutil.which("gettab") is None:
        pytest.skip("gettab not available")
    files = sorted(
        glob.glob(f"{geode_config.ncep_dump.root_path}/gdas.20240101/00/atmos/*.bufr*")
    )
    if not files:
        pytest.skip("no sample BUFR files")
    tree = GenericBufrIngestor()._process(files[0])
    if tree is not None:
        assert tree.attrs["ingestor"] == "generic_bufr"
