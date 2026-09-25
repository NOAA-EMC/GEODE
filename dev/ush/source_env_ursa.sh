#!/bin/bash
# Source this file (do not execute) to load the GEODE modules and activate the
# virtual environment for interactive development on Ursa:
#   source dev/ush/source_env.sh

if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
  echo "ERROR: This script must be sourced, not executed." >&2
  echo "Usage: source ${BASH_SOURCE[0]}" >&2
  exit 1
fi

geode_source_env() {
  local script_dir
  local repo_root
  local modulefile_dir
  local venv_dir

  script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
  repo_root="$(cd "${script_dir}/../.." && pwd)"
  modulefile_dir="${repo_root}/dev/env/modulefiles"
  venv_dir="${repo_root}/.venv"

  if [[ ! -d "${venv_dir}" ]]; then
    echo "ERROR: Virtual environment not found at ${venv_dir}" >&2
    echo "Run dev/ush/create_venv.sh first." >&2
    return 1
  fi

  module use "${modulefile_dir}"
  module load ursa.intel || { echo "ERROR: Failed to load ursa.intel module" >&2; return 1; }

  source "${venv_dir}/bin/activate"
}

geode_source_env
unset -f geode_source_env
