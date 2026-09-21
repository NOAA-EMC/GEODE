import os
import subprocess
from pathlib import Path


def _create_fake_python(fake_python: Path) -> None:
    fake_python.write_text(
        """#!/bin/bash
set -euo pipefail
if [[ "$#" -eq 0 ]]; then
  while IFS= read -r _line; do
    :
  done
  printf '%s\n' "${FAKE_PYTHON_ENV_ACTIVE:-false}"
  exit 0
fi
if [[ "${1:-}" == "-c" ]]; then
  printf '%s\n' "${FAKE_PYTHON_ENV_ACTIVE:-false}"
  exit 0
fi
if [[ "${1:-}" == "-" && "${2:-}" == "active-env" ]]; then
  printf '%s\n' "${FAKE_PYTHON_ENV_ACTIVE:-false}"
  exit 0
fi
if [[ "${1:-}" == "-" && "${2:-}" == "user-site" ]]; then
  printf '%s\n' "${FAKE_PYTHON_USER_SITE_ENABLED:-true}"
  exit 0
fi
{
  printf 'CALL\n'
  for arg in "$@"; do
    printf '%s\n' "$arg"
  done
} >> "${FAKE_PYTHON_LOG}"
""",
        encoding="utf-8",
    )
    fake_python.chmod(0o755)


def test_install_and_test_script_runs_expected_commands(tmp_path):
    script_path = Path(__file__).resolve().parents[1] / "dev" / "ush" / "install_and_test.sh"
    fake_bin = tmp_path / "bin"
    fake_python = fake_bin / "python"
    log_path = tmp_path / "python_calls.log"

    fake_bin.mkdir()
    _create_fake_python(fake_python)

    env = os.environ.copy()
    env["FAKE_PYTHON_LOG"] = str(log_path)
    env["FAKE_PYTHON_ENV_ACTIVE"] = "false"
    env["FAKE_PYTHON_USER_SITE_ENABLED"] = "true"
    env["PATH"] = f"{fake_bin}:{env['PATH']}"

    subprocess.run(["bash", str(script_path)], check=True, env=env)

    assert log_path.read_text(encoding="utf-8").splitlines() == [
        "CALL",
        "-m",
        "pip",
        "install",
        "--user",
        "--no-build-isolation",
        "-e",
        ".[dev]",
        "CALL",
        "-m",
        "pytest",
        "test/",
        "-v",
        "-s",
        "-W",
        "error::pytest.PytestUnhandledThreadExceptionWarning",
    ]


def test_install_and_test_script_omits_user_flag_in_virtualenv(tmp_path):
    script_path = Path(__file__).resolve().parents[1] / "dev" / "ush" / "install_and_test.sh"
    fake_bin = tmp_path / "bin"
    fake_python = fake_bin / "python"
    log_path = tmp_path / "python_calls.log"

    fake_bin.mkdir()
    _create_fake_python(fake_python)

    env = os.environ.copy()
    env["FAKE_PYTHON_LOG"] = str(log_path)
    env["FAKE_PYTHON_ENV_ACTIVE"] = "true"
    env["FAKE_PYTHON_USER_SITE_ENABLED"] = "true"
    env["PATH"] = f"{fake_bin}:{env['PATH']}"

    subprocess.run(["bash", str(script_path)], check=True, env=env)

    assert log_path.read_text(encoding="utf-8").splitlines() == [
        "CALL",
        "-m",
        "pip",
        "install",
        "--no-build-isolation",
        "-e",
        ".[dev]",
        "CALL",
        "-m",
        "pytest",
        "test/",
        "-v",
        "-s",
        "-W",
        "error::pytest.PytestUnhandledThreadExceptionWarning",
    ]


def test_install_and_test_script_fails_for_invalid_python(tmp_path):
    script_path = Path(__file__).resolve().parents[1] / "dev" / "ush" / "install_and_test.sh"
    env = os.environ.copy()
    env["PYTHON"] = str(tmp_path / "missing-python")

    result = subprocess.run(
        ["bash", str(script_path)],
        check=False,
        capture_output=True,
        text=True,
        env=env,
    )

    assert result.returncode != 0
    assert (
        "FATAL ERROR: PYTHON is set but does not resolve to an executable"
        in result.stderr
    )


def test_install_and_test_script_fails_when_user_site_is_unsupported(tmp_path):
    script_path = Path(__file__).resolve().parents[1] / "dev" / "ush" / "install_and_test.sh"
    fake_bin = tmp_path / "bin"
    fake_python = fake_bin / "python"

    fake_bin.mkdir()
    _create_fake_python(fake_python)

    env = os.environ.copy()
    env["FAKE_PYTHON_ENV_ACTIVE"] = "false"
    env["FAKE_PYTHON_USER_SITE_ENABLED"] = "false"
    env["PATH"] = f"{fake_bin}:{env['PATH']}"

    result = subprocess.run(
        ["bash", str(script_path)],
        check=False,
        capture_output=True,
        text=True,
        env=env,
    )

    assert result.returncode != 0
    assert (
        "FATAL ERROR: --user installs are not supported by the selected python interpreter"
        in result.stderr
    )


def test_install_and_test_script_falls_back_to_python3(tmp_path):
    script_path = Path(__file__).resolve().parents[1] / "dev" / "ush" / "install_and_test.sh"
    fake_bin = tmp_path / "bin"
    fake_python3 = fake_bin / "python3"
    log_path = tmp_path / "python_calls.log"

    fake_bin.mkdir()
    _create_fake_python(fake_python3)

    env = os.environ.copy()
    env.pop("PYTHON", None)
    env["FAKE_PYTHON_LOG"] = str(log_path)
    env["FAKE_PYTHON_ENV_ACTIVE"] = "false"
    env["FAKE_PYTHON_USER_SITE_ENABLED"] = "true"
    env["PATH"] = str(fake_bin)

    subprocess.run(
        ["/bin/bash", str(script_path)],
        check=True,
        env=env,
    )

    assert log_path.read_text(encoding="utf-8").splitlines() == [
        "CALL",
        "-m",
        "pip",
        "install",
        "--user",
        "--no-build-isolation",
        "-e",
        ".[dev]",
        "CALL",
        "-m",
        "pytest",
        "test/",
        "-v",
        "-s",
        "-W",
        "error::pytest.PytestUnhandledThreadExceptionWarning",
    ]
