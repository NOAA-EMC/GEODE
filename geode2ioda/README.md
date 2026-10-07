# GEODE → IODA prototype

Prototype for transferring observation data obtained through the GEODE Python
interface into an IODA OSDF `FrameCols`.

Current path:

    GEODE
      ↓
    xarray DataTree
      ↓
    NumPy
      ↓
    pybind11
      ↓
    osdf::FrameCols

The current prototype uses ATMS data and creates:

    MetaData/latitude
    MetaData/longitude
    ObsValue/brightnessTemperature_0 ... _21

This is deliberately separate from `ice2ioda`, which contains the earlier
Icechunk FFI prototype.

## Test

    unset PYTHONPATH
    PYTHONPATH=. pytest -v tests/test_geode_osdf.py
