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


def _parse_tank_id(value: str) -> str:
    from geode.configs.table_a_mapping import format_tank_id, parse_tank_id

    try:
        return format_tank_id(*parse_tank_id(value))
    except ValueError as error:
        raise argparse.ArgumentTypeError(str(error)) from error


def _run_tank_reader(args: argparse.Namespace) -> int:
    from geode.configs.table_a_mapping import UnmappedTankError
    from geode.ingest.consumers.tank_reader import (
        RestrictedTankError,
        TankConfigError,
        TankReader,
    )

    try:
        dataset = TankReader().ingest(args.tank_id, args.start_date, args.end_date)
    except (UnmappedTankError, RestrictedTankError, TankConfigError) as error:
        print(f"geode: error: {error}", file=sys.stderr)
        return 1

    print(f"{args.tank_id} -> {dataset}")
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
        from geode.data.manager import data_manager

        for data_type in data_manager.list_data_types():
            print(data_type)
    if args.list_tank_datasets:
        from geode.configs.table_a_mapping import table_a_mapping

        for tank_id in table_a_mapping.tank_ids():
            info = table_a_mapping.get(tank_id)
            restricted = "\trestricted" if info.restricted else ""
            print(f"{tank_id}\t{info.dataset}\t{info.format}{restricted}")
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

    tank_parser = ingest_parsers.add_parser(
        "tank_reader",
        help="Read NCEP BUFR tank files (bAAA/xxBBB) for a UTC date range.",
    )
    tank_parser.add_argument(
        "tank_id", type=_parse_tank_id, help="BUFR tank ID, e.g. b000/xx001."
    )
    tank_parser.add_argument(
        "start_date", type=_parse_utc_date, help="Start date in YYYY-MM-DD format."
    )
    tank_parser.add_argument(
        "end_date", type=_parse_utc_date, help="End date in YYYY-MM-DD format."
    )
    tank_parser.set_defaults(handler=_run_tank_reader)

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
    admin_parser.add_argument(
        "--list-tank-datasets",
        action="store_true",
        help="List BUFR tank IDs with their dataset, format, and restriction.",
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
