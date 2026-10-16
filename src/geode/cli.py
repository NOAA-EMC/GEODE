import argparse
import datetime
import sys
from collections.abc import Sequence


def _parse_utc_date(value: str) -> datetime.datetime:
    try:
        parsed = datetime.date.fromisoformat(value)
    except ValueError as error:
        raise argparse.ArgumentTypeError(
            f"invalid date '{value}': expected YYYY-MM-DD"
        ) from error

    if value != parsed.isoformat():
        raise argparse.ArgumentTypeError(f"invalid date '{value}': expected YYYY-MM-DD")

    return datetime.datetime.combine(parsed, datetime.time.min, tzinfo=datetime.UTC)


def _run_ncep_dump_reader(args: argparse.Namespace) -> int:
    from geode.ingest.consumers.ncep_dump_reader import NcepDumpReader

    NcepDumpReader().ingest(args.dump_id, args.start_date, args.end_date)
    return 0


def _parse_reference_datetime(value: str) -> datetime.datetime:
    try:
        parsed = datetime.datetime.fromisoformat(value)
    except ValueError as error:
        raise argparse.ArgumentTypeError(
            f"invalid datetime '{value}': expected ISO 8601, e.g. 2026-08-01T12:00:00Z"
        ) from error

    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=datetime.UTC)
    return parsed


def _run_tac_gts_reader(args: argparse.Namespace) -> int:
    from geode.ingest.consumers.tac_gts_reader import TacGTSReader

    TacGTSReader().ingest(
        args.data_type,
        args.file_paths,
        reference_datetime=args.reference_datetime
        or datetime.datetime.now(datetime.UTC),
        include_raw_code=args.include_raw_code,
    )
    return 0


def _run_wis2_listener(_: argparse.Namespace) -> int:
    from geode.ingest.consumers.wis2_listener import Wis2Listener

    Wis2Listener().listen()
    return 0


def _run_admin(args: argparse.Namespace) -> int:
    if args.list_ingestors:
        from geode.ingest import ingestors

        for ingestor in ingestors.directory():
            print(ingestor)
    if args.list_data_types:
        from geode.data.data_manager import data_manager

        for data_type in data_manager.list_data_types():
            print(data_type)
    return 0


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="geode",
        description="Unified command-line interface for GEODE.",
    )
    command_parsers = parser.add_subparsers(dest="command", required=True)

    ingest_parser = command_parsers.add_parser("ingest", help="Run an ingest consumer.")
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

    tac_parser = ingest_parsers.add_parser(
        "tac_gts_reader",
        help="Read TAC GTS (ASCII text) bulletin files for a report type.",
    )
    tac_parser.add_argument("data_type", help="TAC report type, such as 'temp'.")
    tac_parser.add_argument(
        "file_paths", nargs="+", metavar="file_path", help="TAC bulletin file(s)."
    )
    tac_parser.add_argument(
        "--reference-datetime",
        type=_parse_reference_datetime,
        default=None,
        help=(
            "ISO 8601 bulletin receipt time used to resolve day/hour groups "
            "(naive values are treated as UTC). Defaults to the current UTC time."
        ),
    )
    tac_parser.add_argument(
        "--include-raw-code",
        action="store_true",
        help="Include original TAC groups as MetaData/rawCode.",
    )
    tac_parser.set_defaults(handler=_run_tac_gts_reader)

    wis2_parser = ingest_parsers.add_parser(
        "wis2_listener", help="Start the WIS2 notification listener."
    )
    wis2_parser.set_defaults(handler=_run_wis2_listener)

    admin_parser = command_parsers.add_parser("admin", help="Run GEODE admin tasks.")
    admin_parser.add_argument(
        "--list-ingestors", action="store_true", help="List all available ingestors."
    )
    admin_parser.add_argument(
        "--list-data-types",
        action="store_true",
        help="List data types available to the get command.",
    )
    admin_parser.set_defaults(handler=_run_admin)

    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = _build_parser()
    normalized_argv = sys.argv[1:] if argv is None else argv
    args = parser.parse_args(normalized_argv)
    return args.handler(args)


if __name__ == "__main__":
    raise SystemExit(main())
