import datetime
import sys
import types

import pytest

from geode import cli


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
            return types.SimpleNamespace(handler=lambda _: 7)

    monkeypatch.setattr(cli, "_build_parser", lambda: FakeParser())

    assert cli.main(["ingest", "wis2_listener"]) == 7
