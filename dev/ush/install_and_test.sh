#!/bin/bash
set -euo pipefail

using_active_python_env() {
  local python_bin

  python_bin="${1}"

  "${python_bin}" <<'PY'
import os
import sys

base_prefix = getattr(sys, "base_prefix", sys.prefix)
has_virtualenv_prefix = hasattr(sys, "real_prefix") or sys.prefix != base_prefix
has_shell_env = bool(os.environ.get("CONDA_PREFIX") or os.environ.get("VIRTUAL_ENV"))

print("true" if has_virtualenv_prefix or has_shell_env else "false")
PY
}

main() {
  local active_python_env
  local python_bin
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

  python_bin="${PYTHON:-$(command -v python || true)}"
  if [[ -z "${python_bin}" ]]; then
    echo "FATAL ERROR: Could not find a python interpreter" >&2
    exit 1
  fi

  cd "${repo_root}"
  pip_install_args=(--no-build-isolation -e ".[dev]")
  active_python_env="$(using_active_python_env "${python_bin}")"
  if [[ "${active_python_env}" != "true" ]]; then
    pip_install_args=(--user "${pip_install_args[@]}")
  fi

  "${python_bin}" -m pip install "${pip_install_args[@]}"
  "${python_bin}" -m pytest test/ -v -s -W error::pytest.PytestUnhandledThreadExceptionWarning
}

main "$@"
