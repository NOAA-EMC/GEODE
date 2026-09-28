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

## Dependencies

The prototype currently depends on:

* **obsForge** — provides the NOAA build environment and dependency stack
* **OOPS 1.13.0** — required by the current IODA branch
* **IODA** — `icechunk-poc` branch
* **Icechunk** — Rust source from the `main` branch
* **eckit**
* **Rust/Cargo**
* **Python** with the packages required by the test-data conversion script
* **NetCDF** and other IODA dependencies provided by the obsForge environment

The prototype currently uses the NOAA `obsforge/ursa.intel` module environment. Dependency packaging and installation will be addressed separately.

## Environment

The prototype uses the `obsforge/ursa.intel` module environment.
Edit `OBSFORGE_HOME` in `scripts/setup_env.sh` 

Then:

```bash
source scripts/setup_env.sh
```

## Build Dependencies

### 1. Build OOPS

The current IODA branch requires OOPS 1.13.0.

Clone OOPS directly from GitHub and build it separately:

```bash
cd <BUILD_ROOT>

git clone --branch 1.13.0 --depth 1 \
  https://github.com/JCSDA/oops.git oops

mkdir oops-build
cd oops-build

ecbuild \
  --build=Release \
  -DCMAKE_INSTALL_PREFIX=<BUILD_ROOT>/oops-install \
  ../oops

cmake --build . --parallel
cmake --install .
```

### 2. Build IODA

Clone the IODA `icechunk-poc` branch:

```bash
cd <BUILD_ROOT>

git clone -b icechunk-poc https://github.com/JCSDA/ioda.git
```

Configure IODA against the OOPS installation:

```bash
mkdir ioda-build
cd ioda-build

ecbuild \
  --build=Release \
  -DCMAKE_PREFIX_PATH=<BUILD_ROOT>/oops-install \
  ../ioda
```

Build ioda:

```bash
cmake --build . --parallel
```

Or build only ioda engines:

```bash
cmake --build . --target ioda_engines --parallel 8
```


### 4. Build the Icechunk → IODA prototype

The prototype build fetches the Icechunk Rust source automatically if it is not already present.

Edit `IODA_SOURCE_DIR` and `IODA_BUILD_DIR` in `ice2ioda/build.sh`

Then

```bash
cd ice2ioda
./build.sh
```

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
