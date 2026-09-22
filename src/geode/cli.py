import argparse
import datetime
import sys
from collections.abc import Sequence
from pathlib import Path


def _parse_utc_date(value: str) -> datetime.datetime:
    try:
        parsed = datetime.date.fromisoformat(value)
    except ValueError as error:
        raise argparse.ArgumentTypeError(
            f"invalid date '{value}': expected YYYY-MM-DD"
        ) from error

    if value != parsed.isoformat():
        raise argparse.ArgumentTypeError(
            f"invalid date '{value}': expected YYYY-MM-DD"
        )

    return datetime.datetime.combine(
        parsed, datetime.time.min, tzinfo=datetime.UTC
    )


def _run_ncep_dump_reader(args: argparse.Namespace) -> int:
    from geode.ingest.consumers.ncep_dump_reader import NcepDumpReader

    NcepDumpReader().ingest(args.dump_id, args.start_date, args.end_date)
    return 0


def _run_wis2_listener(_: argparse.Namespace) -> int:
    from geode.ingest.consumers.wis2_listener import Wis2Listener

    Wis2Listener().listen()
    return 0


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="geode",
        description="Unified command-line interface for GEODE consumers.",
    )
    command_parsers = parser.add_subparsers(dest="command", required=True)

    ingest_parser = command_parsers.add_parser(
        "ingest", help="Run an ingest consumer."
    )
    ingest_parsers = ingest_parser.add_subparsers(dest="consumer", required=True)

    ncep_dump_parser = ingest_parsers.add_parser(
        "ncep_dump_reader",
        help="Read NCEP dump files for a dump ID and UTC date range.",
    )
    ncep_dump_parser.add_argument("dump_id", help="NCEP dump identifier to ingest.")
    ncep_dump_parser.add_argument(
        "start_date", type=_parse_utc_date, help="Start date in YYYY-MM-DD format."
    )
    ncep_dump_parser.add_argument(
        "end_date", type=_parse_utc_date, help="End date in YYYY-MM-DD format."
    )
    ncep_dump_parser.set_defaults(handler=_run_ncep_dump_reader)

    wis2_parser = ingest_parsers.add_parser(
        "wis2_listener", help="Start the WIS2 notification listener."
    )
    wis2_parser.set_defaults(handler=_run_wis2_listener)

    return parser


def _default_argv() -> list[str]:
    program_name = Path(sys.argv[0]).name
    if program_name in {"geode", "cli.py"}:
        return sys.argv[1:]
    return []


def main(argv: Sequence[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(_default_argv() if argv is None else argv)
    return args.handler(args)


if __name__ == "__main__":
    raise SystemExit(main())
