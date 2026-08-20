import argparse
import json
import os
import sys
import threading
import time

import requests
from pywis_pubsub.mqtt import MQTTPubSubClient

sys.path.append(
    os.path.abspath(os.path.join(os.path.dirname(os.path.dirname(__file__)), "../.."))
)

from geode.configs.geode_config import geode_config
from geode.ingest.ingestors.ingestor_factory import get_ingestor


class Wis2Listener:
    def __init__(self):
        self.topic = geode_config.wis2.topic
        self.download_dir = geode_config.wis2.full_download_dir
        self.broker_url = geode_config.wis2.broker_url
        self.topic = geode_config.wis2.topic

        self.mqtt_client = None
        self.subscribe_thread = None
        self.stop_event = threading.Event()

        # for testing purposes, we can set a callback function to be called when a message is received
        self.on_message_callback = None

        # Ensure the download directory exists
        os.makedirs(self.download_dir, exist_ok=True)

    def listen(self):
        print(f"[*] Connecting to MQTT broker... {self.broker_url}")
        self.stop_event.clear()

        self.mqtt_client = MQTTPubSubClient(
            self.broker_url, options={"verify_certs": True}
        )
        self.mqtt_client.bind("on_message", self._on_message)

        print("[*] Connecting via WSS...")

        # Run subscription in a background thread; client.close() will trigger loop exit.
        self.subscribe_thread = threading.Thread(
            target=self.mqtt_client.sub,
            args=([self.topic],),
            daemon=True,
        )
        self.subscribe_thread.start()

        if geode_config.run_for_num_sec:
            print(f"[*] Download directory: {self.download_dir}")
            try:
                print(
                    f"[*] Running listener (for {geode_config.run_for_num_sec} seconds)."
                )
                start_time = time.time()
                while (
                    time.time() - start_time < geode_config.run_for_num_sec
                    and not self.stop_event.wait(1)
                ):
                    pass
            finally:
                print("[*] Disconnecting...")
                if self.mqtt_client:
                    self.mqtt_client.close()
                self.mqtt_client = None
                self._join_subscribe_thread()

    def stop(self):
        """Stop the listener."""
        print("[*] Quitting listener...")
        self.stop_event.set()
        if self.mqtt_client:
            self.mqtt_client.close()
            self.mqtt_client = None

        self._join_subscribe_thread()

    def _join_subscribe_thread(self):
        """Wait for the subscription thread unless called from that thread."""
        if (
            self.subscribe_thread
            and self.subscribe_thread is not threading.current_thread()
        ):
            self.subscribe_thread.join(timeout=5)
            self.subscribe_thread = None

    # ==========================================
    # MQTT Callbacks
    # ==========================================

    def _on_message(self, client, userdata, msg):
        """Fired when a new message is published to the subscribed topic."""
        # Double-check that we are only processing messages from our target topic tree
        # (Helpful if you add more subscriptions later)
        if not msg.topic.startswith(self.topic[:-2]):
            return

        payload_str = msg.payload.decode("utf-8")
        print(f"\n[*] Notification received on {msg.topic}")

        try:
            data = json.loads(payload_str)
        except json.JSONDecodeError:
            print("[-] Invalid payload format: Message must be valid JSON")
            return

        wis_id = os.path.join(msg.topic.split("/")[-2], msg.topic.split("/")[-1])
        print(f"[*] WIS ID: {wis_id}")

        def _get_file_download_info(data):
            """Extracts the download URL and filename from the WIS2 notification payload."""
            url = None
            filename = None

            # Parse standard WIS2 Notification Message (GeoJSON)
            # The download link is typically found in the 'links' array
            if "links" in data:
                for link in data.get("links", []):
                    if (
                        link.get("rel") in {"canonical", "update"}
                        and link.get("type") == "application/bufr"
                        and link.get("href")
                    ):
                        url = link["href"]
                        filename = os.path.basename(requests.utils.urlparse(url).path)
                        break

            # Fallback for the older simple schema, just in case
            if not url:
                url = data.get("url")
                filename = data.get("filename")

            return url, filename

        file_url, file_name = _get_file_download_info(data)

        # Use WIS ID as subdirectory name, replacing slashes with underscores
        downloaded_file_path = self._download_file(file_url, file_name, wis_id)

        if not downloaded_file_path:
            return

        # Process the downloaded file with the appropriate ingestor if available
        ingestor_class = get_ingestor(wis_id)

        if ingestor_class:
            ingestor = ingestor_class()
            ingestor.process(downloaded_file_path)

        if self.on_message_callback:
            self.on_message_callback()

    def _download_file(self, url: str, filename: str, sub_dir: str) -> str:
        try:
            print(f"[*] Starting download: {url}")

            # stream=True ensures we don't load huge files entirely into memory
            response = requests.get(url, stream=True, timeout=15)
            response.raise_for_status()

            # Sanitize filename
            safe_filename = os.path.basename(filename)
            filepath = os.path.join(
                geode_config.wis2.full_download_dir, sub_dir, safe_filename
            )

            # ensure the directory exists
            os.makedirs(os.path.dirname(filepath), exist_ok=True)

            temporary_filepath = f"{filepath}.part"
            with open(temporary_filepath, "wb") as f:
                f.writelines(response.iter_content(chunk_size=8192))
            os.replace(temporary_filepath, filepath)

            print(f"[+] Successfully saved to: {filepath}")
            return filepath

        except requests.exceptions.RequestException as e:
            print(f"[-] Network error downloading {url}: {e}")
            return ""
        except OSError as e:
            print(f"[-] Error saving file: {e}")
            return ""


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="MQTT Listener for WIS2 Notifications")
    args = parser.parse_args()

    listener = Wis2Listener()
    listener.listen()
