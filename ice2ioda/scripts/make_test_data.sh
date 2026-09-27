#!/bin/bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"

DATA_DIR="${ROOT_DIR}/data"
PYTHON_ENV="${ROOT_DIR}/.venv"

INPUT_NC="${1:?Usage: $0 INPUT.nc OUTPUT.icechunk}"
OUTPUT_ICECHUNK="${2:?Usage: $0 INPUT.nc OUTPUT.icechunk}"

# Create a local Python environment if necessary.
if [ ! -x "${PYTHON_ENV}/bin/python" ]; then
    echo "Creating Python environment: ${PYTHON_ENV}"
    python3 -m venv "${PYTHON_ENV}"

    "${PYTHON_ENV}/bin/python" -m pip install --upgrade pip
    "${PYTHON_ENV}/bin/python" -m pip install \
        icechunk \
        xarray \
        zarr \
        netCDF4
fi

mkdir -p "${DATA_DIR}"

"${PYTHON_ENV}/bin/python" \
    "${SCRIPT_DIR}/netcdf_to_icechunk.py" \
    "${INPUT_NC}" \
    "${DATA_DIR}/${OUTPUT_ICECHUNK}"

echo
echo "Created:"
echo "  ${DATA_DIR}/${OUTPUT_ICECHUNK}"
