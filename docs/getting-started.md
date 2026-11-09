# Getting Started

This project is structured around the `geode` package under `src/geode`.

## Prerequisites

- Python 3.10 or newer
- `pip` for package installation

## Installation

From the repository root, install GEODE in editable mode:

```bash
python -m pip install -e .
```

If you are developing GEODE locally, install with development extras:

```bash
python -m pip install -e ".[dev]"
```

This installs GEODE and registers the `geode` command-line entry point.

## Dependencies

### Required runtime dependencies

GEODE runtime dependencies are managed in `pyproject.toml` under
`[project].dependencies`:

- `icechunk==2.1.2`
- `netCDF4`
- `pywis-pubsub==0.12.0`
- `PyYAML`
- `requests==2.34.2`
- `SQLAlchemy`
- `wxflow==0.4.2`
- `xarray>=2025.8.0`

### Optional dependencies

Optional dependencies are managed in `pyproject.toml` under
`[project.optional-dependencies]`.

- `dev` extras:
  - `pytest==9.1.1`
  - `ruff==0.16.3`

Install optional dependencies with:

```bash
python -m pip install -e ".[dev]"
```

## Running tests with pytest

Run tests from the repository root:

```bash
python -m pytest test/ -v
```

The CI workflow runs:

```bash
python -m pytest test/ -v -s -W error::pytest.PytestUnhandledThreadExceptionWarning
```

## Package layout

The main areas of the package are:

- `geode.geode` for the top-level retrieval API
- `geode.configs` for configuration objects and validation
- `geode.data` for data lake managers
- `geode.ingest` for ingestors and WIS2 listeners
- `geode.model` for model-level abstractions

## Quick usage

```python
from datetime import datetime
from geode.geode import get

start = datetime(2024, 1, 1)
end = datetime(2024, 1, 2)

data = get("surface-based-observations/synop", start, end)
print(data)
```

## Configuration

The configuration is loaded from the YAML files in the `configs/` directory. The configuration classes in `geode.configs` define the available lake types, database settings, and WIS2 ingest options.

### BUFR tanks

To ingest NCEP BUFR tanks, add a `bufr_tank` section to `geode.yaml`:

```yaml
bufr_tank:
  root_path: "/path/to/tanks"
  include_restricted: false
  allow_unmapped: false
```

| Option | Description |
|---|---|
| `root_path` | Directory containing the tanks, laid out as `YYYYMMDD/bAAA/xxBBB` |
| `include_restricted` | Allow tanks marked restricted in `table_a_mapping.yaml` |
| `allow_unmapped` | Allow tanks that are not in `table_a_mapping.yaml`, stored under the name `bAAA_xxBBB` |

See [BUFR Tanks](bufr-tanks.md) for how tanks are stored.
