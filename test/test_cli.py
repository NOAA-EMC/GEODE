import builtins
import datetime
import runpy
import sys
import types

import pytest

from geode import cli
from geode.ingest import ingestors


def _install_fake_consumer_module(monkeypatch, module_name, class_name, consumer_class):
    fake_module = types.ModuleType(module_name)
    setattr(fake_module, class_name, consumer_class)
    monkeypatch.setitem(sys.modules, module_name, fake_module)


def test_geode_cli_dispatches_ncep_dump_reader(monkeypatch):
    recorded_call = {}

    class FakeReader:
        def ingest(self, dump_id, start_date, end_date):
            recorded_call["dump_id"] = dump_id
            recorded_call["start_date"] = start_date
            recorded_call["end_date"] = end_date

    _install_fake_consumer_module(
        monkeypatch,
        "geode.ingest.consumers.ncep_dump_reader",
        "NcepDumpReader",
        FakeReader,
    )

    exit_code = cli.main(
        ["ingest", "ncep_dump_reader", "atms", "2026-08-01", "2026-09-02"]
    )

    assert exit_code == 0
    assert recorded_call == {
        "dump_id": "atms",
        "start_date": datetime.datetime(2026, 8, 1, tzinfo=datetime.UTC),
        "end_date": datetime.datetime(2026, 9, 2, tzinfo=datetime.UTC),
    }


def test_geode_cli_dispatches_tank_reader(monkeypatch, capsys):
    recorded_call = {}

    class FakeReader:
        def ingest(self, tank_id, start_date, end_date):
            recorded_call["tank_id"] = tank_id
            recorded_call["start_date"] = start_date
            recorded_call["end_date"] = end_date
            return "surface_synop"

    from geode.ingest.consumers import tank_reader

    monkeypatch.setattr(tank_reader, "TankReader", FakeReader)

    exit_code = cli.main(
        ["ingest", "tank_reader", "/b000/xx001/", "2026-08-01", "2026-08-02"]
    )

    assert exit_code == 0
    assert recorded_call == {
        "tank_id": "b000/xx001",
        "start_date": datetime.datetime(2026, 8, 1, tzinfo=datetime.UTC),
        "end_date": datetime.datetime(2026, 8, 2, tzinfo=datetime.UTC),
    }
    assert capsys.readouterr().out == "b000/xx001 -> surface_synop\n"


def test_geode_cli_rejects_invalid_tank_id(capsys):
    with pytest.raises(SystemExit) as error:
        cli.main(["ingest", "tank_reader", "surface_synop", "2026-08-01", "2026-08-02"])

    assert error.value.code == 2
    assert "bAAA/xxBBB" in capsys.readouterr().err


@pytest.mark.parametrize(
    ("error_name", "message"),
    [
        ("UnmappedTankError", "BUFR tank 'b000/xx999' is not defined"),
        ("RestrictedTankError", "BUFR tank 'b000/xx000' is restricted"),
        ("TankConfigError", "No 'tank' section in geode.yaml"),
    ],
)
def test_geode_cli_reports_tank_errors_without_traceback(
    monkeypatch, capsys, error_name, message
):
    from geode.configs import table_a_mapping
    from geode.ingest.consumers import tank_reader

    error_class = getattr(tank_reader, error_name, None) or getattr(
        table_a_mapping, error_name
    )

    class FailingReader:
        def __init__(self):
            raise error_class(message)

    monkeypatch.setattr(tank_reader, "TankReader", FailingReader)

    exit_code = cli.main(
        ["ingest", "tank_reader", "b000/xx999", "2026-08-01", "2026-08-02"]
    )

    captured = capsys.readouterr()
    assert exit_code == 1
    assert captured.out == ""
    assert captured.err == f"geode: error: {message}\n"


def test_geode_cli_lets_unexpected_tank_errors_propagate(monkeypatch):
    from geode.ingest.consumers import tank_reader

    class BrokenReader:
        def ingest(self, *args):
            raise RuntimeError("decoder blew up")

    monkeypatch.setattr(tank_reader, "TankReader", BrokenReader)

    with pytest.raises(RuntimeError, match="decoder blew up"):
        cli.main(["ingest", "tank_reader", "b000/xx001", "2026-08-01", "2026-08-02"])


def test_geode_cli_lists_tank_datasets(capsys):
    assert cli.main(["admin", "--list-tank-datasets"]) == 0
    lines = capsys.readouterr().out.splitlines()

    assert "b000/xx001\tsurface_synop\tWMO FM-12 SYNOP" in lines
    assert "b000/xx000\tsurface_synop_restricted\tWMO FM-12 SYNOP\trestricted" in lines


def test_geode_cli_dispatches_wis2_listener(monkeypatch):
    call_count = 0

    class FakeListener:
        def listen(self):
            nonlocal call_count
            call_count += 1

    _install_fake_consumer_module(
        monkeypatch,
        "geode.ingest.consumers.wis2_listener",
        "Wis2Listener",
        FakeListener,
    )

    exit_code = cli.main(["ingest", "wis2_listener"])

    assert exit_code == 0
    assert call_count == 1


def test_geode_cli_lists_ingestors(capsys, monkeypatch):
    monkeypatch.setattr(ingestors, "directory", lambda: ["bufr", "netcdf"])

    assert cli.main(["admin", "--list-ingestors"]) == 0
    assert capsys.readouterr().out == "bufr\nnetcdf\n"


def test_geode_cli_lists_data_types(capsys, monkeypatch):
    fake_data_manager_module = types.ModuleType("geode.data.manager")
    fake_data_manager_module.data_manager = types.SimpleNamespace(
        list_data_types=lambda: ["atms_n20", "amsua_n19"]
    )
    monkeypatch.setitem(sys.modules, "geode.data.manager", fake_data_manager_module)

    assert cli.main(["admin", "--list-data-types"]) == 0
    assert capsys.readouterr().out == "atms_n20\namsua_n19\n"


def test_geode_cli_rejects_invalid_dates(capsys):
    with pytest.raises(SystemExit) as error:
        cli.main(["ingest", "ncep_dump_reader", "atms", "2026-8-01", "2026-09-02"])

    assert error.value.code == 2
    assert "expected YYYY-MM-DD" in capsys.readouterr().err


def test_geode_cli_requires_a_command(capsys):
    with pytest.raises(SystemExit) as error:
        cli.main([])

    assert error.value.code == 2
    assert "the following arguments are required: command" in capsys.readouterr().err


def test_geode_cli_rejects_unknown_consumer(capsys):
    with pytest.raises(SystemExit) as error:
        cli.main(["ingest", "unknown_consumer"])

    assert error.value.code == 2
    assert "invalid choice" in capsys.readouterr().err


def test_geode_cli_returns_handler_exit_code(monkeypatch):
    class FakeParser:
        def parse_args(self, argv):
            assert argv == ["ingest", "wis2_listener"]
            parsed_args = types.SimpleNamespace()

            def handler(received_args):
                assert received_args is parsed_args
                return 7

            parsed_args.handler = handler
            return parsed_args

    monkeypatch.setattr(cli, "_build_parser", lambda: FakeParser())

    assert cli.main(["ingest", "wis2_listener"]) == 7


def test_geode_cli_main_uses_process_argv(monkeypatch):
    call_count = 0

    class FakeListener:
        def listen(self):
            nonlocal call_count
            call_count += 1

    _install_fake_consumer_module(
        monkeypatch,
        "geode.ingest.consumers.wis2_listener",
        "Wis2Listener",
        FakeListener,
    )
    monkeypatch.setattr(sys, "argv", ["geode", "ingest", "wis2_listener"])

    assert cli.main() == 0
    assert call_count == 1


def test_geode_cli_surfaces_lazy_import_failures(monkeypatch):
    original_import = builtins.__import__

    def fake_import(name, globals=None, locals=None, fromlist=(), level=0):
        if name == "geode.ingest.consumers.ncep_dump_reader":
            raise ModuleNotFoundError("No module named 'bufr'")
        return original_import(name, globals, locals, fromlist, level)

    monkeypatch.setattr(builtins, "__import__", fake_import)

    with pytest.raises(ModuleNotFoundError, match="bufr"):
        cli.main(["ingest", "ncep_dump_reader", "atms", "2026-08-01", "2026-09-02"])


def test_geode_cli_module_entrypoint_dispatches_wis2_listener(monkeypatch):
    call_count = 0

    class FakeListener:
        def listen(self):
            nonlocal call_count
            call_count += 1

    _install_fake_consumer_module(
        monkeypatch,
        "geode.ingest.consumers.wis2_listener",
        "Wis2Listener",
        FakeListener,
    )
    monkeypatch.delitem(sys.modules, "geode.cli", raising=False)
    monkeypatch.setattr(sys, "argv", ["geode", "ingest", "wis2_listener"])

    with pytest.raises(SystemExit) as error:
        runpy.run_module("geode.cli", run_name="__main__")

    assert error.value.code == 0
    assert call_count == 1
