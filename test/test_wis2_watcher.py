import os
import sys
import time
from pathlib import Path

import paho.mqtt.client as mqtt

sys.path.append(
    os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "src")
)  # Add src/ to sys.path

from geode.ingest import watcher


def test_wis2_watcher(tmp_path: Path):
    """Test that the WIS2 watcher successfully connects, listens, and downloads .bufr4 files."""
    # Override watcher's download directory to use pytest's tmp_path
    watcher.DOWNLOAD_DIR = str(tmp_path)

    client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, transport="websockets")  # Use websockets for port 443

    # Add the WIS2 public credentials here
    client.username_pw_set("everyone", "everyone")

    # Enable TLS/SSL (Crucial for port 8883)
    client.tls_set()

    client.on_connect = watcher.on_connect
    client.on_message = watcher.on_message

    print(f"[*] Connecting to {watcher.BROKER_ADDRESS} with TLS...")
    client.connect(watcher.BROKER_ADDRESS, watcher.BROKER_PORT, keepalive=60)

    client.loop_start()
    try:
        print(
            "[*] Running listener (up to 120 seconds) or until a .bufr4 file is downloaded..."
        )
        start_time = time.time()
        while time.time() - start_time < 120:
            # Check if any .bufr4 files exist in tmp_path
            downloaded_files = list(tmp_path.glob("*.bufr4"))
            if downloaded_files:
                print(f"[+] Found downloaded .bufr4 files: {downloaded_files}")
                break
            time.sleep(1)
    finally:
        print("[*] Stopping loop and disconnecting...")
        client.loop_stop()
        client.disconnect()

    # Assert that at least some files ending in .bufr4 were downloaded
    downloaded_files = list(tmp_path.glob("*.bufr4"))
    assert len(downloaded_files) > 0, (
        "No .bufr4 files were downloaded within 60 seconds."
    )
