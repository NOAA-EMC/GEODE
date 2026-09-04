import argparse

from geode.ingest import ingestors


def _print_ingestors():
    for ingestor in ingestors.directory():
        print(ingestor)


def main():
    parser = argparse.ArgumentParser(description="Admin interface for GEODE.")
    parser.add_argument(
        "--list-ingestors", action="store_true", help="List all available ingestors."
    )
    args = parser.parse_args()

    if args.list_ingestors:
        _print_ingestors()


if __name__ == "__main__":
    main()
