#!/bin/bash
set -euo pipefail

using_active_python_env() {
  local python_bin

  python_bin="${1}"

  "${python_bin}" <<'PY'
import sys

base_prefix = getattr(sys, "base_prefix", sys.prefix)
has_virtualenv_prefix = hasattr(sys, "real_prefix") or sys.prefix != base_prefix

print("true" if has_virtualenv_prefix else "false")
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

  if [[ -n "${PYTHON:-}" ]]; then
    if command -v "${PYTHON}" >/dev/null 2>&1; then
      python_bin="$(command -v "${PYTHON}")"
    elif [[ -x "${PYTHON}" ]]; then
      python_bin="${PYTHON}"
    else
      echo "FATAL ERROR: PYTHON is set but does not resolve to an executable: ${PYTHON}" >&2
      exit 1
    fi
  else
    python_bin="$(command -v python || true)"
    if [[ -z "${python_bin}" ]]; then
      python_bin="$(command -v python3 || true)"
    fi
  fi

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
