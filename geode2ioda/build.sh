#!/bin/bash
set -e

cmake -S . -B build \
  -Dpybind11_DIR=/contrib/spack-stack/spack-stack-1.9.2/envs/ue-oneapi-2024.2.1/install/oneapi/2024.2.1/py-pybind11-2.13.5-jlasn3w/share/cmake/pybind11 \
  -DCMAKE_CXX_COMPILER=icpx

cmake --build build
