import icechunk as ic
import numpy as np
import pytest
import xarray as xr
import yaml
import zarr

from geode.data.manager.icechunk import AppendSchemaError, IceChunkDataManager
from geode.ingest.ingestors.bufr_tank import (
    drop_empty_rows,
    finalize_tree,
    join_raw_report,
    level_variables,
    use_variable_length_strings,
)


def _datasets(pressure, wind):
    root = xr.Dataset(coords={"Location": np.arange(len(pressure))})
    meta = xr.Dataset({"pressure": ("Location", np.array(pressure, dtype=float))})
    obs = xr.Dataset({"windSpeed": ("Location", np.array(wind, dtype=float))})
    return {"/": root, "/MetaData": meta, "/ObsValue": obs}


LEVELS = ["MetaData/pressure", "ObsValue/windSpeed"]


def test_level_variables_only_returns_grouped_sequence(tmp_path):
    config = {
        "bufr": {
            "group_by_variable": "pressure",
            "variables": {
                "latitude": {"query": "*/CLAT"},
                "pressure": {"query": "*/UARLV/PRLC"},
                "windSpeed": {"query": "*/UARLV/UAWND/WSPD"},
            },
        },
        "encoder": {
            "variables": [
                {"name": "MetaData/latitude", "source": "variables/latitude"},
                {"name": "MetaData/pressure", "source": "variables/pressure"},
                {"name": "ObsValue/windSpeed", "source": "variables/windSpeed"},
            ]
        },
    }
    path = tmp_path / "tank.yaml"
    path.write_text(yaml.safe_dump(config))
    assert level_variables(str(path)) == LEVELS


def test_level_variables_is_empty_without_grouping(tmp_path):
    path = tmp_path / "tank.yaml"
    path.write_text(yaml.safe_dump({"bufr": {"variables": {}}, "encoder": {}}))
    assert level_variables(str(path)) == []


def test_drop_empty_rows_keeps_data_with_missing_coordinate():
    datasets = _datasets([100.0, np.nan, np.nan], [np.nan, 5.0, np.nan])
    result = drop_empty_rows(datasets, LEVELS)
    assert result["/MetaData"].sizes["Location"] == 2
    assert result["/ObsValue"].windSpeed.values[1] == 5.0
    assert result["/"].sizes["Location"] == 2


def test_drop_empty_rows_without_level_variables_is_unchanged():
    datasets = _datasets([np.nan], [np.nan])
    assert drop_empty_rows(datasets, [])["/MetaData"].sizes["Location"] == 1


def test_join_raw_report_preserves_spaces_between_pieces():
    root = xr.Dataset(coords={"Location": [0, 1], "RawReportChunk": [0, 1]})
    pieces = np.array([["KDCA 300", "000Z"], ["", ""]], dtype=object)
    meta = xr.Dataset({"rawReportString": (("Location", "RawReportChunk"), pieces)})

    result = join_raw_report({"/": root, "/MetaData": meta})

    assert result["/MetaData"].rawReport.dims == ("Location",)
    assert result["/MetaData"].rawReport.values.tolist() == ["KDCA 300000Z", ""]
    assert "rawReportString" not in result["/MetaData"]
    assert "RawReportChunk" not in result["/"].variables


def test_join_raw_report_handles_a_file_with_no_reports():
    root = xr.Dataset(coords={"Location": np.array([], dtype=int)})
    meta = xr.Dataset({"rawReportString": ("Location", np.array([], dtype=object))})

    result = join_raw_report({"/": root, "/MetaData": meta})

    assert "rawReportString" not in result["/MetaData"]
    assert result["/MetaData"].rawReport.dims == ("Location",)
    assert result["/MetaData"].rawReport.size == 0


def test_strings_become_variable_length_and_lose_fixed_width_encoding():
    data = xr.DataArray(np.array(["ABC", "DE"]), dims="Location", attrs={"a": 1})
    data.encoding["dtype"] = data.dtype
    data.encoding["chunksizes"] = (2,)
    meta = xr.Dataset({"name": data, "value": ("Location", np.array([1.0, 2.0]))})

    result = use_variable_length_strings({"/MetaData": meta})["/MetaData"]

    assert result["name"].dtype == object
    assert result["name"].values.tolist() == ["ABC", "DE"]
    assert result["name"].attrs == {"a": 1}
    assert "dtype" not in result["name"].encoding
    assert result["name"].encoding["chunksizes"] == (2,)
    assert result["value"].dtype == float


def test_finalize_tree_returns_none_when_all_rows_are_empty():
    tree = xr.DataTree.from_dict(_datasets([np.nan], [np.nan]))
    assert finalize_tree(tree, LEVELS) is None


def _tree(names, size=2):
    meta = xr.Dataset({name: ("Location", np.arange(size)) for name in names})
    root = xr.Dataset(coords={"Location": np.arange(size)})
    return xr.DataTree.from_dict({"/": root, "/MetaData": meta})


def _manager(tmp_path, monkeypatch):
    manager = IceChunkDataManager()
    path = str(tmp_path / "data.icechunk")
    monkeypatch.setattr(manager, "get_file_path", lambda *args, **kwargs: path)
    return manager, path


def test_append_rejects_missing_variable_and_leaves_store_unchanged(
    tmp_path, monkeypatch
):
    manager, path = _manager(tmp_path, monkeypatch)
    manager.put("data", _tree(["a", "b"]))

    with pytest.raises(AppendSchemaError, match=r"Missing from new data: \['b'\]"):
        manager.put("data", _tree(["a"]))

    repo = ic.Repository.open(ic.local_filesystem_storage(path))
    root = zarr.open_group(repo.readonly_session("main").store, mode="r")
    assert root["MetaData/a"].shape == (2,)
    assert root["MetaData/b"].shape == (2,)


def test_append_rejects_new_variable(tmp_path, monkeypatch):
    manager, _ = _manager(tmp_path, monkeypatch)
    manager.put("data", _tree(["a"]))

    with pytest.raises(AppendSchemaError, match=r"Not in store: \['b'\]"):
        manager.put("data", _tree(["a", "b"]))


def test_append_with_matching_variables_extends_store(tmp_path, monkeypatch):
    manager, path = _manager(tmp_path, monkeypatch)
    manager.put("data", _tree(["a", "b"]))
    manager.put("data", _tree(["a", "b"], size=3))

    repo = ic.Repository.open(ic.local_filesystem_storage(path))
    root = zarr.open_group(repo.readonly_session("main").store, mode="r")
    assert root["MetaData/a"].shape == (5,)
