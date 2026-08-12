import os
import sys
import threading
import time
from importlib.util import find_spec
from pathlib import Path
from types import ModuleType
from typing import ClassVar

import pytest

sys.path.append(
    os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "src")
)  # Add src/ to sys.path

from geode.ingest import watcher


def test_build_broker_url_defaults(monkeypatch) -> None:
    """Test that the watcher uses the default websocket endpoint."""
    monkeypatch.delenv("WIS2_BROKER_USERNAME", raising=False)
    monkeypatch.delenv("WIS2_BROKER_PASSWORD", raising=False)
    monkeypatch.delenv("WIS2_BROKER_WEBSOCKET_PATH", raising=False)

    broker_url = watcher._build_broker_url()

    assert watcher.BROKER_HOST in broker_url
    assert f":{watcher.BROKER_PORT}/mqtt" in broker_url


def test_run_uses_configured_websocket_path(monkeypatch, tmp_path: Path) -> None:
    """Test that run wires the MQTT client with the configured websocket path."""

    class DummyClient:
        instances: ClassVar[list["DummyClient"]] = []

        def __init__(self, broker_url: str) -> None:
            self.broker_url = broker_url
            self.bound_events: dict[str, object] = {}
            self.subscribed_topics: list[str] = []
            DummyClient.instances.append(self)

        def bind(self, event: str, function) -> None:
            self.bound_events[event] = function

        def sub(self, topics: list[str]) -> None:
            self.subscribed_topics = topics

    pywis_pubsub_module = ModuleType("pywis_pubsub")
    mqtt_module = ModuleType("pywis_pubsub.mqtt")
    mqtt_module.MQTTPubSubClient = DummyClient
    pywis_pubsub_module.mqtt = mqtt_module

    monkeypatch.setitem(sys.modules, "pywis_pubsub", pywis_pubsub_module)
    monkeypatch.setitem(sys.modules, "pywis_pubsub.mqtt", mqtt_module)
    monkeypatch.setattr(watcher, "DOWNLOAD_DIR", str(tmp_path))
    monkeypatch.setenv("WIS2_BROKER_WEBSOCKET_PATH", "wis2")

    topics = ["origin/a/wis2/test"]
    watcher.run(topics)

    assert len(DummyClient.instances) == 1
    client = DummyClient.instances[0]
    assert client.broker_url.endswith("/wis2")
    assert client.subscribed_topics == topics
    assert "on_message" in client.bound_events


def test_wis2_watcher(tmp_path: Path):
    """Test that the WIS2 watcher successfully connects, listens, and downloads .bufr4 files."""
    if os.getenv("RUN_WIS2_WATCHER_INTEGRATION_TEST") != "1":
        pytest.skip(
            "Set RUN_WIS2_WATCHER_INTEGRATION_TEST=1 to run the live watcher test."
        )
    if find_spec("pywis_pubsub") is None:
        pytest.skip("pywis-pubsub is required for the live watcher test.")

    # Override watcher's download directory to use pytest's tmp_path
    watcher.DOWNLOAD_DIR = str(tmp_path)

    t = threading.Thread(target=watcher.run, daemon=True)
    t.start()

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

    # Assert that at least some files ending in .bufr4 were downloaded
    downloaded_files = list(tmp_path.glob("*.bufr4"))
    assert len(downloaded_files) > 0, (
        "No .bufr4 files were downloaded within 180 seconds."
    )
