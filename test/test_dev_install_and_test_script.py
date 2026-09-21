import os
import subprocess
from pathlib import Path


def test_install_and_test_script_runs_expected_commands(tmp_path):
    script_path = Path(__file__).resolve().parents[1] / "dev" / "ush" / "install_and_test.sh"
    fake_bin = tmp_path / "bin"
    fake_python = fake_bin / "python"
    log_path = tmp_path / "python_calls.log"

    fake_bin.mkdir()
    fake_python.write_text(
        """#!/bin/bash
set -euo pipefail
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

    env = os.environ.copy()
    env["FAKE_PYTHON_LOG"] = str(log_path)
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
    fake_python.write_text(
        """#!/bin/bash
set -euo pipefail
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

    env = os.environ.copy()
    env["FAKE_PYTHON_LOG"] = str(log_path)
    env["PATH"] = f"{fake_bin}:{env['PATH']}"
    env["VIRTUAL_ENV"] = str(tmp_path / "venv")

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
