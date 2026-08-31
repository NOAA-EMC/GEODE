"""Command-line interface for GEODE."""

import argparse
import pprint
from importlib.resources import as_file, files

from geode.utils.bufr_table import BufrCodeFlag, BufrTableB

TABLE_B_RESOURCE = files("geode.data.resources").joinpath("BUFRCREX_TableB_en.txt")
CODE_FLAG_RESOURCE = files("geode.data.resources").joinpath("BUFRCREX_CodeFlag_en.txt")


def main(arguments: list[str] | None = None) -> None:
    """Run the GEODE command-line interface.

    Parameters
    ----------
    arguments : list[str] | None
        Command-line arguments excluding the program name. When omitted, use
        the process command-line arguments.

    Examples
    --------
    >>> main(["info", "bufr", "001003"])
    """
    parser = argparse.ArgumentParser(prog="geode")
    command_parsers = parser.add_subparsers(dest="command", required=True)

    info_parser = command_parsers.add_parser("info", help="Show metadata.")
    info_parsers = info_parser.add_subparsers(dest="info_type", required=True)
    bufr_parser = info_parsers.add_parser("bufr", help="Show BUFR Table B metadata.")
    bufr_parser.add_argument("fxy", help="Six-digit BUFR Table B descriptor.")
    bufr_parser.add_argument(
        "code_figure",
        nargs="?",
        help="Optional BUFR code figure for a CodeFlag table lookup.",
    )

    parsed_arguments = parser.parse_args(arguments)
    if parsed_arguments.command == "info" and parsed_arguments.info_type == "bufr":
        if parsed_arguments.code_figure is None:
            with as_file(TABLE_B_RESOURCE) as table_b_path:
                table = BufrTableB(table_b_path)
                try:
                    entry = table.entry(parsed_arguments.fxy)
                except ValueError as error:
                    parser.error(str(error))
                except KeyError:
                    parser.error(
                        f"Unknown BUFR Table B descriptor: {parsed_arguments.fxy}"
                    )
        else:
            with as_file(CODE_FLAG_RESOURCE) as code_flag_path:
                table = BufrCodeFlag(code_flag_path)
                lookup = (
                    f"{parsed_arguments.fxy} code figure {parsed_arguments.code_figure}"
                )
                try:
                    entry = table.entry(
                        parsed_arguments.fxy, parsed_arguments.code_figure
                    )
                except ValueError as error:
                    parser.error(str(error))
                except KeyError:
                    parser.error(f"Unknown BUFR CodeFlag entry: {lookup}")
        pprint.pprint(entry, sort_dicts=False)
