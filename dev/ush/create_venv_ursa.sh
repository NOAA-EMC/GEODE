#!/bin/bash
# Create a Python virtual environment on Ursa for GEODE development.
# Loads the ursa.intel modulefile, then builds a venv on top of it using pyproject.toml.
set -eo pipefail

main() {
  local script_path
  local script_dir
  local repo_root
  local modulefile_dir
  local venv_dir

  script_path="${BASH_SOURCE[0]}"
  if [[ "${script_path}" == */* ]]; then
    script_dir="$(cd "${script_path%/*}" && pwd)"
  else
    script_dir="$(pwd)"
  fi
  repo_root="$(cd "${script_dir}/../.." && pwd)"
  modulefile_dir="${repo_root}/dev/env/modulefiles"
  venv_dir="${repo_root}/.venv"

  if [[ ! -f "${repo_root}/pyproject.toml" ]]; then
    echo "FATAL ERROR: Could not find pyproject.toml in ${repo_root}" >&2
    exit 1
  fi

  if [[ ! -f "${modulefile_dir}/ursa.intel.lua" ]]; then
    echo "FATAL ERROR: Could not find ursa.intel.lua in ${modulefile_dir}" >&2
    exit 1
  fi

  module use "${modulefile_dir}"
  module load ursa.intel || { echo "FATAL ERROR: Failed to load ursa.intel module" >&2; exit 1; }
  module list

  if [[ -d "${venv_dir}" ]]; then
    echo "FATAL ERROR: Virtual environment already exists at ${venv_dir}" >&2
    echo "Remove it first if you want to recreate it." >&2
    exit 1
  fi

  echo "Creating virtual environment at ${venv_dir}"
  python3 -m venv --system-site-packages "${venv_dir}"

  set +eo pipefail
  source "${venv_dir}/bin/activate"
  set -eo pipefail

  # The ursa.intel module puts its own pip/setuptools/wheel on PYTHONPATH, which
  # takes precedence over the venv's site-packages and shadows the upgraded
  # build tools below. Strip those specific entries, keeping the rest so
  # module-provided packages (numpy, netCDF4, xarray, etc.) are still found.
  export PYTHONPATH="$(echo "${PYTHONPATH:-}" | tr ':' '\n' | grep -Ev '/py-(pip|setuptools|wheel)-' | paste -sd: -)"

  python -m pip install --upgrade pip setuptools wheel
  python -m pip install --no-build-isolation -e "${repo_root}[dev]"

  deactivate

  echo "Virtual environment created at ${venv_dir}"
  echo "Use dev/ush/source_env.sh to load the modules and activate it in the future."
}

main "$@"
