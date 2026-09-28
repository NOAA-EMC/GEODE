#!/bin/bash
set -euo pipefail  # Exit immediately on error, unset variables, or pipe failures

I2I_ROOT="/scratch3/NCEPDEV/da/Edward.Givelberg/i2i"
IODA_SOURCE_DIR="${I2I_ROOT}/ioda"
IODA_BUILD_DIR="${I2I_ROOT}/ioda-build"

# Ensure output build directory exists
mkdir -p build

# Configure CMake
cmake -S . -B build \
  -DCMAKE_BUILD_TYPE=Release \
  -DIODA_SOURCE_DIR="${IODA_SOURCE_DIR}" \
  -DIODA_BUILD_DIR="${IODA_BUILD_DIR}"

# Build with multi-core parallelism
cmake --build build --parallel "$(nproc 2>/dev/null || sysctl -n hw.ncpu 2>/dev/null || echo 4)"
