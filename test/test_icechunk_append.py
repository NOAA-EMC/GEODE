import icechunk as ic
import numpy as np
import pytest
import xarray as xr
import zarr

from geode.data.manager.icechunk import AppendSchemaError, IceChunkDataManager


def _tree(names, size=2):
    meta = xr.Dataset({name: ("Location", np.arange(size)) for name in names})
    root = xr.Dataset(coords={"Location": np.arange(size)})
    return xr.DataTree.from_dict({"/": root, "/MetaData": meta})


def _manager(tmp_path, monkeypatch):
    manager = IceChunkDataManager()
    path = str(tmp_path / "data.icechunk")
    monkeypatch.setattr(manager, "get_file_path", lambda *args, **kwargs: path)
    return manager, path


def _stored(path):
    repo = ic.Repository.open(ic.local_filesystem_storage(path))
    return zarr.open_group(repo.readonly_session("main").store, mode="r")


def test_append_rejects_missing_variable_and_leaves_store_unchanged(
    tmp_path, monkeypatch
):
    manager, path = _manager(tmp_path, monkeypatch)
    manager.put("data", _tree(["a", "b"]))

    with pytest.raises(AppendSchemaError, match=r"Missing from new data: \['b'\]"):
        manager.put("data", _tree(["a"]))

    root = _stored(path)
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

    assert _stored(path)["MetaData/a"].shape == (5,)


def test_empty_repository_from_an_interrupted_write_is_treated_as_new(
    tmp_path, monkeypatch
):
    manager, path = _manager(tmp_path, monkeypatch)
    ic.Repository.create(ic.local_filesystem_storage(path))

    manager.put("data", _tree(["a"]))

    assert _stored(path)["MetaData/a"].shape == (2,)
