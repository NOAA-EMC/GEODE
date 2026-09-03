# GEODE: Geospatial Earth Observation Data Engine

Next-Generation observation ingest, data store, and processing framework.
   
<!-- CC0 1.0 License -->
[![License: CC0-1.0](https://img.shields.io/badge/License-CC0_1.0-lightgrey.svg)](http://creativecommons.org/publicdomain/zero/1.0/)

<!-- Last Commit -->
[![GitHub last commit](https://img.shields.io/github/last-commit/noaa-emc/geode)](https://github.com/noaa-emc/geode/commits/develop)

<!-- GitHub Actions CI/CD -->
[![Python Tests on GitHub CI](https://github.com/noaa-emc/geode/actions/workflows/run_pytests.yaml/badge.svg)](https://github.com/noaa-emc/geode/actions/workflows/run_pytests.yaml)
[![Coding Norms](https://github.com/noaa-emc/geode/actions/workflows/linter.yaml/badge.svg)](https://github.com/noaa-emc/geode/actions/workflows/linter.yaml)
[![Weekly Container Build](https://github.com/noaa-emc/geode/actions/workflows/build-container.yaml/badge.svg)](https://github.com/noaa-emc/geode/actions/workflows/build-container.yaml)

## Documentation
See our online documentation page [here](https://noaa-emc.github.io/GEODE/)

## Install

From the repository root:

```bash
python -m pip install -e .
```

To include optional development tools (for testing/linting):

```bash
python -m pip install -e ".[dev]"
```

## Dependencies

- Required runtime dependencies are defined in `pyproject.toml` under `[project].dependencies`
- Optional development dependencies are defined under `[project.optional-dependencies].dev`

## Run tests

From the repository root:

```bash
python -m pytest test/ -v -s -W error::pytest.PytestUnhandledThreadExceptionWarning
```

## License

This project is part of NOAA-EMC Ecosystem. 

See LICENSE and DISCLAIMER for details.
