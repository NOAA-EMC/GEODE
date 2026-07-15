"""Tests for test/get_data.py script."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path


def test_download_adpsfc(tmp_path: Path) -> None:
    """Test that get_data.py successfully downloads adpsfc data to a temporary location."""
    script_path = Path(__file__).parent / "get_data.py"

    # Run the script using the current python executable
    result = subprocess.run(
        [
            sys.executable,
            str(script_path),
            "--bufr-type",
            "adpsfc",
            "--output-dir",
            str(tmp_path),
        ],
        capture_output=True,
        text=True,
        check=True,
    )

    # Print the output for debugging/logging in case of failure
    print(result.stdout)
    print(result.stderr, file=sys.stderr)

    # Verify that the standard output mentions download completion
    assert "Download complete" in result.stdout

    # Verify that the downloaded file exists in tmp_path and is not empty
    downloaded_files = list(tmp_path.glob("*.bufr_d*"))
    assert len(downloaded_files) == 1

    downloaded_file = downloaded_files[0]
    assert downloaded_file.exists()
    assert downloaded_file.name.endswith(".adpsfc.tm00.bufr_d.nr")
    assert downloaded_file.stat().st_size > 0
