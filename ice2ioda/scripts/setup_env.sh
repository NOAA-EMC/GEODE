#!/bin/bash

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

OBSFORGE_HOME="/scratch3/NCEPDEV/da/Edward.Givelberg/obsForge"

module use "${OBSFORGE_HOME}/modulefiles"
module load obsforge/ursa.intel

# export LD_LIBRARY_PATH="${SCRIPT_DIR}/src/icechunk-ffi/target/release:${LD_LIBRARY_PATH:-}"


ICECHUNK_FFI_DIR="$(cd "${SCRIPT_DIR}/../src/icechunk-ffi" && pwd)"
export LD_LIBRARY_PATH="${ICECHUNK_FFI_DIR}:${LD_LIBRARY_PATH:-}"
