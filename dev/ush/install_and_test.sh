#!/bin/bash
set -euo pipefail

main() {
  local active_python_env
  local script_dir
  local repo_root
  local -a pip_install_args

  script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
  repo_root="$(cd "${script_dir}/../.." && pwd)"

  if [[ ! -f "${repo_root}/pyproject.toml" ]]; then
    echo "FATAL ERROR: Could not find pyproject.toml in ${repo_root}" >&2
    exit 1
  fi

  if [[ ! -d "${repo_root}/test" ]]; then
    echo "FATAL ERROR: Could not find test directory in ${repo_root}" >&2
    exit 1
  fi

  cd "${repo_root}"
  pip_install_args=(--no-build-isolation -e ".[dev]")
  active_python_env="$(
    python -c 'import os, sys; print("true" if (hasattr(sys, "real_prefix") or sys.prefix != getattr(sys, "base_prefix", sys.prefix) or os.environ.get("CONDA_PREFIX") or os.environ.get("VIRTUAL_ENV")) else "false")'
  )"
  if [[ "${active_python_env}" != "true" ]]; then
    pip_install_args=(--user "${pip_install_args[@]}")
  fi

  python -m pip install "${pip_install_args[@]}"
  python -m pytest test/ -v -s -W error::pytest.PytestUnhandledThreadExceptionWarning
}

main "$@"
