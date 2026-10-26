# GEODE Repository Guidance

GEODE is a Python system for ingesting, storing, and retrieving Earth
observations for operational workflows, including data assimilation. Keep
changes reliable for repeatable production runs and large observation volumes.

## Architecture and Data Contracts

- **Package layout:** Application code is under `src/geode`. Configuration
  classes are in `src/geode/configs`, ingestion consumers and ingestors are in
  `src/geode/ingest`, and storage and retrieval are in `src/geode/data` and
  `src/geode/client.py`.
- **Ingest flow:** Consumers such as the NCEP dump reader and WIS2 listener
  dispatch input files to registered ingestors. Follow these existing
  boundaries when adding formats or sources; keep source-specific parsing out
  of shared storage and retrieval code.
- **Observation formats:** Handle BUFR and other supported observation formats
  through the existing parsing and conversion paths. Preserve observation
  values, metadata, dimensions, units, timestamps, and missing-value semantics
  during conversion.
- **Data trees:** Ingestors store `xarray.DataTree` data. The current Icechunk
  writer processes nodes with a `Location` dimension, and retrieval applies
  time filtering using `MetaData/dateTime`. Preserve these structures when
  changing ingest schemas or storage behavior, and cover schema changes with
  tests.
- **Storage:** Icechunk is the primary data-lake backend; configuration also
  supports other backends. Keep backend-specific behavior within the data
  manager, use repository transactions for Icechunk writes, and test
  read/write compatibility when changing stored layouts.
- **Scale and operations:** Avoid unbounded eager reads or collecting large
  observation sets in memory. Stream file transfers where practical, validate
  inputs and configuration at boundaries, and report failures clearly rather
  than silently dropping data.
- **Configuration:** Keep deployment-specific paths, lake settings, and ingest
  options in the existing YAML configuration and configuration classes; do
  not hardcode operational paths or credentials.

## Development and Validation

- **Python support:** `pyproject.toml` is authoritative for supported Python
  versions and dependencies.
- **Install for development:** `python -m pip install -e ".[dev]"`.
- **Focused tests:** `python -m pytest test/test_<area>.py -q`.
- **Full test suite:** `python -m pytest test/ -v -s -W error::pytest.PytestUnhandledThreadExceptionWarning`.
- **Formatting and lint:** `ruff format --check src/geode test` and
  `ruff check src/geode test`.
- **Test behavior:** Add or update tests for ingest parsing, data-tree
  structure, storage round trips, time-boundary behavior, and retrieval as
  applicable. Keep unit tests deterministic; mock external brokers and
  downloads rather than depending on live services.

## Project References

- Start with [README.md](README.md) and the [documentation](docs/index.md) for
  usage and API details.
- Follow the repository-wide guidance in
  [.github/copilot-instructions.md](.github/copilot-instructions.md) and the
  applicable language guidance in `.github/instructions/`.

## 🛑 Boundaries & Constraints

- **Never** commit raw data files (`.nc`, `.bin`, `.bufr`) to the repository.
- **Do not** bypass Icechunk's transactional API by modifying raw Zarr metadata components directly on object storage.
- **Do not** append data to the `main` storage branch without going through a validated ingestion pipeline transaction.
