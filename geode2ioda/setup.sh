#!/bin/bash

module load rdhpcs-python/3.13
module load intel-oneapi-compilers/2024.2.1
module load cmake/3.30.2

unset PYTHONPATH

# Avoid re-activating the venv if this script is sourced
# from a shell that already has it active.
if [[ -n "${VIRTUAL_ENV:-}" ]]; then
    deactivate
fi

source ../venv/bin/activate

# Native libraries required by IODA
IODA_LIB_DIR=/scratch3/NCEPDEV/da/Edward.Givelberg/i2i/ioda-build/lib
MKL_LIB_DIR=/apps/spack-2024-12/linux-rocky9-x86_64/gcc-11.4.1/intel-oneapi-mkl-2024.2.1-srqwrbzwo2k7hxuuhlrxttburs5jvlat/mkl/2024.2/lib

export LD_LIBRARY_PATH="${IODA_LIB_DIR}:${MKL_LIB_DIR}:${LD_LIBRARY_PATH:-}"
