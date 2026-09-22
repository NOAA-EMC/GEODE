import datetime
import inspect

import pytest

import geode
from geode import cli


def test_main_dispatches_ncep_dump_reader(monkeypatch: pytest.MonkeyPatch) -> None:
    observed: dict[str, object] = {}

    class FakeReader:
        def ingest(
            self,
            dump_id: str,
            start_date: datetime.datetime,
            end_date: datetime.datetime,
        ) -> None:
            observed["dump_id"] = dump_id
            observed["start_date"] = start_date
            observed["end_date"] = end_date

    monkeypatch.setattr(cli, "_create_ncep_dump_reader", lambda: FakeReader())

    assert (
        cli.main(
            ["ingest", "ncep_dump_reader", "atms", "2026-08-01", "2026-08-02"]
        )
        == 0
    )
    assert observed == {
        "dump_id": "atms",
        "start_date": datetime.datetime(2026, 8, 1, tzinfo=datetime.UTC),
        "end_date": datetime.datetime(2026, 8, 2, tzinfo=datetime.UTC),
    }


def test_main_dispatches_wis2_listener(monkeypatch: pytest.MonkeyPatch) -> None:
    observed = {"listen_called": False}

    class FakeListener:
        def listen(self) -> None:
            observed["listen_called"] = True

    monkeypatch.setattr(cli, "_create_wis2_listener", lambda: FakeListener())

    assert cli.main(["ingest", "wis2_listener"]) == 0
    assert observed["listen_called"] is True


def test_geode_get_preserves_public_signature() -> None:
    assert list(inspect.signature(geode.get).parameters) == [
        "data_type",
        "start_time",
        "end_time",
        "vars",
        "filter",
    ]


def test_main_uses_sys_argv_for_ncep_dump_reader(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    observed: dict[str, object] = {}

    class FakeReader:
        def ingest(
            self,
            dump_id: str,
            start_date: datetime.datetime,
            end_date: datetime.datetime,
        ) -> None:
            observed["dump_id"] = dump_id
            observed["start_date"] = start_date
            observed["end_date"] = end_date

    monkeypatch.setattr(cli, "_create_ncep_dump_reader", lambda: FakeReader())
    monkeypatch.setattr(
        "sys.argv",
        ["geode", "ingest", "ncep_dump_reader", "atms", "2026-08-01", "2026-08-02"],
    )

    assert cli.main() == 0
    assert observed == {
        "dump_id": "atms",
        "start_date": datetime.datetime(2026, 8, 1, tzinfo=datetime.UTC),
        "end_date": datetime.datetime(2026, 8, 2, tzinfo=datetime.UTC),
    }


def test_main_uses_sys_argv_when_arguments_are_omitted(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    observed = {"listen_called": False}

    class FakeListener:
        def listen(self) -> None:
            observed["listen_called"] = True

    monkeypatch.setattr(cli, "_create_wis2_listener", lambda: FakeListener())
    monkeypatch.setattr("sys.argv", ["geode", "ingest", "wis2_listener"])

    assert cli.main() == 0
    assert observed["listen_called"] is True


def test_main_rejects_invalid_date(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as exc_info:
        cli.main(["ingest", "ncep_dump_reader", "atms", "2026-8-01", "2026-08-02"])

    assert exc_info.value.code == 2
    assert "expected YYYY-MM-DD" in capsys.readouterr().err


@pytest.mark.parametrize(
    ("arguments", "message"),
    [
        ([], "the following arguments are required: command"),
        (["ingest"], "the following arguments are required: consumer"),
        (["unknown"], "invalid choice"),
    ],
)
def test_main_reports_argparse_errors(
    arguments: list[str], message: str, capsys: pytest.CaptureFixture[str]
) -> None:
    with pytest.raises(SystemExit) as exc_info:
        cli.main(arguments)

    assert exc_info.value.code == 2
    assert message in capsys.readouterr().err
