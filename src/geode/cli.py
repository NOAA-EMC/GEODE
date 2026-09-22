import argparse
import datetime
import re
import sys
from collections.abc import Sequence
from typing import Any

_DATE_PATTERN = re.compile(r"\d{4}-\d{2}-\d{2}")


def _parse_date(value: str) -> datetime.datetime:
    if not _DATE_PATTERN.fullmatch(value):
        raise argparse.ArgumentTypeError(
            f"invalid date value: {value!r} (expected YYYY-MM-DD)"
        )

    try:
        return datetime.datetime.strptime(value, "%Y-%m-%d").replace(
            tzinfo=datetime.UTC
        )
    except ValueError as exc:
        raise argparse.ArgumentTypeError(
            f"invalid date value: {value!r} (expected YYYY-MM-DD)"
        ) from exc


def _create_ncep_dump_reader() -> Any:
    from geode.ingest.consumers.ncep_dump_reader import NcepDumpReader

    return NcepDumpReader()


def _create_wis2_listener() -> Any:
    from geode.ingest.consumers.wis2_listener import Wis2Listener

    return Wis2Listener()


def _run_ncep_dump_reader(args: argparse.Namespace) -> int:
    _create_ncep_dump_reader().ingest(args.dump_id, args.start_date, args.end_date)
    return 0


def _run_wis2_listener(_: argparse.Namespace) -> int:
    _create_wis2_listener().listen()
    return 0


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="geode", description="GEODE command-line interface."
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    ingest_parser = subparsers.add_parser(
        "ingest", help="Run an ingest consumer.", description="Run an ingest consumer."
    )
    ingest_subparsers = ingest_parser.add_subparsers(dest="consumer", required=True)

    ncep_dump_reader_parser = ingest_subparsers.add_parser(
        "ncep_dump_reader",
        help="Ingest NCEP dump files for a dump ID and date range.",
        description="Ingest NCEP dump files for a dump ID and date range.",
    )
    ncep_dump_reader_parser.add_argument(
        "dump_id", help="NCEP dump identifier, such as 'atms'."
    )
    ncep_dump_reader_parser.add_argument(
        "start_date", type=_parse_date, help="Start date in YYYY-MM-DD format."
    )
    ncep_dump_reader_parser.add_argument(
        "end_date", type=_parse_date, help="End date in YYYY-MM-DD format."
    )
    ncep_dump_reader_parser.set_defaults(handler=_run_ncep_dump_reader)

    wis2_listener_parser = ingest_subparsers.add_parser(
        "wis2_listener",
        help="Start the WIS2 MQTT listener.",
        description="Start the WIS2 MQTT listener.",
    )
    wis2_listener_parser.set_defaults(handler=_run_wis2_listener)

    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = _build_parser()
    normalized_argv = sys.argv[1:] if argv is None else argv
    args = parser.parse_args(normalized_argv)
    return args.handler(args)


if __name__ == "__main__":
    sys.exit(main())
