import os
import sys
import threading
import time
from pathlib import Path

from pywis_pubsub.mqtt import MQTTPubSubClient

sys.path.append(
    os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "src")
)  # Add src/ to sys.path

from geode.ingest import watcher
from geode.configs.geode_config import geode_config

# RFC1738 broker URL: wss scheme enables websockets transport + TLS on port 443.
# The /mqtt path is required for the broker's websocket upgrade endpoint.
# 'everyone'/'everyone' are the publicly documented WIS2 Global Broker credentials.
BROKER_URL = (
    "wss://"
    + "everyone"
    + ":"
    + "everyone"
    + "@"
    + watcher.BROKER_ADDRESS
    + ":"
    + str(watcher.BROKER_PORT)
    + "/mqtt"
)

def test_wis2_watcher():
   
    tmp_path = Path(geode_config.wis2.full_download_dir)  # Use the download directory from the config

    """Test that the WIS2 watcher successfully connects, listens, and downloads .bufr4 files."""
    # Override watcher's download directory to use pytest's tmp_path
    watcher.DOWNLOAD_DIR = str(tmp_path)

    client = MQTTPubSubClient(BROKER_URL, options={"verify_certs": True})

    client.bind("on_message", watcher.on_message)

    print(
        f"[*] Connecting to {watcher.BROKER_ADDRESS}:{watcher.BROKER_PORT} via WSS..."
    )

    # Run subscription in a background thread; client.close() will trigger loop exit.
    subscribe_thread = threading.Thread(
        target=client.sub,
        args=([watcher.TOPIC],),
        daemon=True,
    )
    subscribe_thread.start()

    try:
        print(
            "[*] Running listener (up to 180 seconds) or until a .bufr4 file is downloaded..."
        )
        start_time = time.time()
        while time.time() - start_time < 180:
            downloaded_files = list(tmp_path.glob("*.bufr4"))
            if downloaded_files:
                print(f"[+] Found downloaded .bufr4 files: {downloaded_files}")
                break
            time.sleep(1)
    finally:
        print("[*] Disconnecting...")
        # close() calls disconnect(), which causes loop_forever() to return and
        # the subscribe_thread to exit cleanly.
        client.close()
        subscribe_thread.join(timeout=5)

    # Assert that at least one .bufr4 file was downloaded
    downloaded_files = list(tmp_path.glob("*.bufr4"))
    assert len(downloaded_files) > 0, (
        "No .bufr4 files were downloaded within 180 seconds."
    )

if __name__ == "__main__":
    test_wis2_watcher()
