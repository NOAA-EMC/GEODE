import json
import os
import sys
from urllib.parse import quote

import requests

# ==========================
# MQTT Client Configuration
# TODO: Move this externally to a config file
# or environment variables for better security and flexibility
# =========================
BROKER_HOST = "wis2node.globaldata.nws.noaa.gov"
BROKER_PORT = 443
BROKER_WEBSOCKET_PATH = "/mqtt"
TOPIC = "origin/a/wis2/+/data/core/weather/surface-based-observations/#"
DOWNLOAD_DIR = "./wis2-data-tmp"

# Ensure the download directory exists
os.makedirs(DOWNLOAD_DIR, exist_ok=True)


# ==========================================
# Core Functions
# ==========================================
def download_file(url, filename):
    """Downloads a file over HTTP(S) and saves it locally."""
    try:
        print(f"[*] Starting download: {url}")

        # stream=True ensures we don't load huge files entirely into memory
        response = requests.get(url, stream=True, timeout=15)
        response.raise_for_status()

        # Sanitize filename
        safe_filename = os.path.basename(filename)
        filepath = os.path.join(DOWNLOAD_DIR, safe_filename)

        temporary_filepath = f"{filepath}.part"
        with open(temporary_filepath, "wb") as f:
            f.writelines(response.iter_content(chunk_size=8192))
        os.replace(temporary_filepath, filepath)

        print(f"[+] Successfully saved to: {filepath}")

    except requests.exceptions.RequestException as e:
        print(f"[-] Network error downloading {url}: {e}")
    except OSError as e:
        print(f"[-] Error saving file: {e}")


# ==========================================
# MQTT Callbacks
# ==========================================
def _make_on_message(subscribed_topics: list[str]):
    """Return an on_message callback that filters to ``subscribed_topics``."""

    # Build a tuple of prefixes to guard against unexpected broker routing
    prefixes = tuple(t.rstrip("#").rstrip("/") for t in subscribed_topics)

    def on_message(client, userdata, msg):
        """Fired when a new message is published to the subscribed topic."""
        # Defensive filter: only process messages from our subscribed topic tree
        if prefixes and not any(msg.topic.startswith(p) for p in prefixes):
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
            download_file(url, filename)
        else:
            print("[-] Could not find a valid download URL in the payload.")
            print(
                f"    Payload excerpt: {payload_str[:200]}..."
            )  # Print first 200 chars for debugging

    return on_message


def _build_broker_url() -> str:
    """Build the WIS2 broker URL with a valid websocket path."""

    username = quote(os.getenv("WIS2_BROKER_USERNAME", "everyone"), safe="")
    password = quote(os.getenv("WIS2_BROKER_PASSWORD", "everyone"), safe="")
    websocket_path = os.getenv(
        "WIS2_BROKER_WEBSOCKET_PATH", BROKER_WEBSOCKET_PATH
    ).strip()

    if not websocket_path:
        websocket_path = BROKER_WEBSOCKET_PATH
    if not websocket_path.startswith("/"):
        websocket_path = f"/{websocket_path}"

    return f"wss://{username}:{password}@{BROKER_HOST}:{BROKER_PORT}{websocket_path}"


# ==========================================
# Entrypoint
# ==========================================
def run(topics: list[str] | None = None) -> None:
    """Subscribe to WIS2 topics and process incoming notifications.

    :param topics: list of MQTT topic strings to subscribe to.
                   Defaults to :data:`TOPIC` when ``None``.
    """
    if topics is None:
        topics = [TOPIC]

    os.makedirs(DOWNLOAD_DIR, exist_ok=True)

    try:
        from pywis_pubsub.mqtt import MQTTPubSubClient
    except ModuleNotFoundError as exc:
        print(
            "FATAL ERROR: pywis-pubsub must be installed to run the WIS2 watcher.",
            file=sys.stderr,
        )
        raise RuntimeError(
            "pywis_pubsub import failed; install pywis-pubsub before running the "
            "WIS2 watcher."
        ) from exc

    client = MQTTPubSubClient(_build_broker_url())
    client.bind("on_message", _make_on_message(topics))

    print(f"[*] Subscribing to topics: {topics}")
    client.sub(topics)
