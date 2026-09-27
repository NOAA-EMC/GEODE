# Icechunk → IODA Proof of Concept

Minimal proof-of-concept for reading native Icechunk data through IODA.

```text
Icechunk → Rust → C ABI → C++ → IODA
```

## Clone

```bash
git clone -b poc/ice2ioda https://github.com/NOAA-EMC/GEODE.git
cd GEODE/ice2ioda
```

## Environment

Edit `OBSFORGE_HOME` in:

```text
scripts/setup_env.sh
```

Then:

```bash
source scripts/setup_env.sh
```

## Dependencies

The prototype currently uses:

* IODA (`icechunk-poc` branch)
* Icechunk
* eckit
* Rust/Cargo
* Python
* `obsforge/ursa.intel` module environment

## Build

```bash
./build.sh
```

CMake fetches Icechunk if needed.

## Test data

```bash
scripts/make_test_data.sh /path/to/argo.nc argo.icechunk
```

Creates:

```text
data/argo.icechunk
```

## Run

```bash
build/ice_ioda_test data/argo.icechunk
```
