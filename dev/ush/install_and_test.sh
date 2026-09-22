#!/bin/bash
set -euo pipefail

main() {
  local script_path
  local script_dir
  local repo_root

  script_path="${BASH_SOURCE[0]}"
  if [[ "${script_path}" == */* ]]; then
    script_dir="$(cd "${script_path%/*}" && pwd)"
  else
    script_dir="$(pwd)"
  fi
  repo_root="$(cd "${script_dir}/../.." && pwd)"

  if [[ ! -f "${repo_root}/pyproject.toml" ]]; then
    echo "FATAL ERROR: Could not find pyproject.toml in ${repo_root}" >&2
    exit 1
  fi

  if [[ ! -d "${repo_root}/test" ]]; then
    echo "FATAL ERROR: Could not find test directory in ${repo_root}" >&2
    exit 1
  fi

  (
    cd "${repo_root}"
    python -m pip install --user --no-build-isolation -e ".[dev]"
    python -m pytest test/ -v -s -W error::pytest.PytestUnhandledThreadExceptionWarning
  )
}

main "$@"
