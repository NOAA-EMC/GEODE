import os
import sys
sys.path.append(os.path.dirname(os.path.dirname(__file__)))

import json
import time
import argparse

import requests
import paho.mqtt.client as mqtt

from configs.geode_config import GeodeConfig
from ingest.atms_ingestor import AtmsIngestor
# from ingest.synop_ingestor import SynopIngestor

ingestors = {
    # 'synop': SynopIngestor,
    'atms': AtmsIngestor
}


class MqttListener:
    def __init__(self, geode_config: GeodeConfig):
        self.broker_address = geode_config.mqtt.broker_address
        self.broker_port = geode_config.mqtt.broker_port
        self.use_websockets = geode_config.mqtt.use_websockets
        self.topic = geode_config.mqtt.topic
        self.download_dir = geode_config.mqtt.download_dir

        # Ensure the download directory exists
        os.makedirs(self.download_dir, exist_ok=True)


    def listen(self):
        print (f"[*] Connecting to MQTT broker at {self.broker_address}:{self.broker_port}...")

        if self.use_websockets:
            client = mqtt.Client(callback_api_version=mqtt.CallbackAPIVersion.VERSION2, transport="websockets")
        else:
            client = mqtt.Client(callback_api_version=mqtt.CallbackAPIVersion.VERSION2)

        # Add the WIS2 public credentials here
        client.username_pw_set("everyone", "everyone")

        # Enable TLS/SSL (Crucial for port 8883)
        client.tls_set()

        client.on_connect = self._on_connect
        client.on_message = self._on_message

        client.connect(self.broker_address, self.broker_port, keepalive=60)

        client.loop_start()
        try:
            print(
                "[*] Running listener (up to 120 seconds) or until a .bufr4 file is downloaded..."
            )
            start_time = time.time()
            while time.time() - start_time < 120:
                # Check if any .bufr4 files exist in tmp_path
                downloaded_files = [f for f in os.listdir(self.download_dir) if f.endswith(".bufr4")]
                if downloaded_files:
                    print(f"[+] Found downloaded .bufr4 files: {downloaded_files}")
                    break
                time.sleep(1)
        finally:
            print("[*] Stopping loop and disconnecting...")
            client.loop_stop()
            client.disconnect()
            

    # ==========================================
    # MQTT Callbacks
    # ==========================================
    def _on_connect(self, client, userdata, flags, reason_code, properties):
        """Fired when the client successfully connects to the broker."""
        if reason_code == 0:
            print(f"[+] Connected to MQTT broker at {self.broker_address}:{self.broker_port}")
            client.subscribe(self.topic)
            print(f"[*] Subscribed to topic: {self.topic}")
        else:
            print(f"[-] Connection failed with code {reason_code}")


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

        if url and filename:
            self._download_file(url, filename)
        else:
            print("[-] Could not find a valid download URL in the payload.")
            print(
                f"    Payload excerpt: {payload_str[:200]}..."
            )  # Print first 200 chars for debugging


    def _download_file(self, url, filename):
        """Downloads a file over HTTP(S) and saves it locally."""
        try:
            print(f"[*] Starting download: {url}")

            # stream=True ensures we don't load huge files entirely into memory
            response = requests.get(url, stream=True, timeout=15)
            response.raise_for_status()

            # Sanitize filename
            safe_filename = os.path.basename(filename)
            filepath = os.path.join(self.download_dir, safe_filename)

            temporary_filepath = f"{filepath}.part"
            with open(temporary_filepath, "wb") as f:
                f.writelines(response.iter_content(chunk_size=8192))
            os.replace(temporary_filepath, filepath)

            print(f"[+] Successfully saved to: {filepath}")

        except requests.exceptions.RequestException as e:
            print(f"[-] Network error downloading {url}: {e}")
        except OSError as e:
            print(f"[-] Error saving file: {e}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="MQTT Listener for WIS2 Notifications")
    parser.add_argument(
        "--config",
        type=str,
        default=os.path.join(os.path.dirname(__file__), "../configs/geode_config.yaml"),
        help="Path to the Geode configuration YAML file",
    )
    
    args = parser.parse_args()
    geode_config = GeodeConfig(args.config)

    listener = MqttListener(geode_config)
    listener.listen()
