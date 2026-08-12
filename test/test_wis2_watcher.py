import os
import sys
import threading
import time
from pathlib import Path

sys.path.append(
    os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "src")
)  # Add src/ to sys.path

from geode.ingest import watcher


def test_wis2_watcher(tmp_path: Path):
    """Test that the WIS2 watcher successfully connects, listens, and downloads .bufr4 files."""
    # Override watcher's download directory to use pytest's tmp_path
    watcher.DOWNLOAD_DIR = str(tmp_path)

    t = threading.Thread(target=watcher.run, daemon=True)
    t.start()

    print(
        "[*] Running listener (up to 120 seconds) or until a .bufr4 file is downloaded..."
    )
    start_time = time.time()
    while time.time() - start_time < 120:
        downloaded_files = list(tmp_path.glob("*.bufr4"))
        if downloaded_files:
            print(f"[+] Found downloaded .bufr4 files: {downloaded_files}")
            break
        time.sleep(1)

    # Assert that at least some files ending in .bufr4 were downloaded
    downloaded_files = list(tmp_path.glob("*.bufr4"))
    assert len(downloaded_files) > 0, (
        "No .bufr4 files were downloaded within 120 seconds."
    )
