"""Command-line interface for GEODE."""

import argparse
import pprint
from pathlib import Path

from geode.utils.bufr_table import BufrTableB

TABLE_B_PATH = (
	Path(__file__).resolve().parents[2]
	/ "parm"
	/ "wmo-bufr4"
	/ "txt"
	/ "BUFRCREX_TableB_en.txt"
)


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

	parsed_arguments = parser.parse_args(arguments)
	if parsed_arguments.command == "info" and parsed_arguments.info_type == "bufr":
		table = BufrTableB(TABLE_B_PATH)
		try:
			entry = table.entry(parsed_arguments.fxy)
		except (KeyError, ValueError) as error:
			parser.error(str(error))
		pprint.pprint(entry, sort_dicts=False)
