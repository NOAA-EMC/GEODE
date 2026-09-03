import argparse

from geode.ingest import ingestors


def main():
    parser = argparse.ArgumentParser(description="Admin interface for GEODE.")
    parser.add_argument(
        "--list-ingestors",
        action="store_true",
        help="List all available ingestors."
    )
    args = parser.parse_args()

    if args.list_ingestors:
        import pprint
        pprint.pprint(ingestors.directory())


if __name__ == "__main__":
    main()
