# Icechunk → IODA Proof of Concept

Minimal proof-of-concept for reading native Icechunk data through IODA.

```text
Icechunk → Rust → C ABI → C++ → IODA
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

## Build Dependencies

### 1. Build obsForge

Clone obsForge with its submodules:

```bash
git clone --recursive --jobs 2 https://github.com/NOAA-EMC/obsForge.git
cd obsForge
./build.sh
```

The obsForge build provides the environment and dependencies needed by the prototype.

### 2. Build OOPS

The current IODA branch requires OOPS 1.13.0.

Use the OOPS source provided by obsForge and build it separately. For example, if obsForge was installed as `<OBSFORGE_DIR>`:

```bash
mkdir -p <BUILD_ROOT>/oops-build
cd <BUILD_ROOT>/oops-build

ecbuild \
  --build=Release \
  -DCMAKE_INSTALL_PREFIX=<BUILD_ROOT>/oops-install \
  <OBSFORGE_DIR>/bundle/oops

cmake --build . --parallel
cmake --install .
```

Here:

* `<OBSFORGE_DIR>` is the location of the obsForge checkout.
* `<BUILD_ROOT>` is a directory used for external builds and installations.

### 3. Build IODA

Clone the IODA `icechunk-poc` branch:

```bash
cd <BUILD_ROOT>

git clone -b icechunk-poc https://github.com/JCSDA/ioda.git
```

Build IODA against the OOPS installation:

```bash
mkdir ioda-build
cd ioda-build

ecbuild \
  --build=Release \
  -DCMAKE_PREFIX_PATH=<BUILD_ROOT>/oops-install \
  ../ioda

cmake --build . --parallel
```


## Clone

```bash
git clone -b poc/ice2ioda https://github.com/NOAA-EMC/GEODE.git
cd GEODE/ice2ioda
```

## Environment

The prototype uses the `obsforge/ursa.intel` module environment.
Edit `OBSFORGE_HOME` in `scripts/setup_env.sh` 

Then:

```bash
source scripts/setup_env.sh
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
