"""Tests for the WIS2 MQTT watcher module.

These tests mock the external MQTT broker connection and HTTP download so
that the watcher's subscription and message-handling logic can be validated
in CI without requiring network access.
"""

from __future__ import annotations

import json
import os
import sys
import types
from pathlib import Path
from unittest.mock import MagicMock, patch

sys.path.append(
    os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "src")
)  # Add src/ to sys.path

from geode.ingest import watcher


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_fake_wis2_notification(url: str, filename: str) -> str:
    """Return a minimal WIS2 Notification Message JSON string.

    Parameters
    ----------
    url : str
        The canonical download href for the data file.
    filename : str
        Base filename (unused in the payload but kept for clarity).

    Returns
    -------
    str
        JSON-encoded WIS2 notification payload.
    """
    return json.dumps(
        {
            "type": "Feature",
            "geometry": None,
            "properties": {"pubtime": "2024-01-01T00:00:00Z"},
            "links": [
                {
                    "rel": "canonical",
                    "type": "application/bufr",
                    "href": url,
                }
            ],
        }
    )


# ---------------------------------------------------------------------------
# Unit tests
# ---------------------------------------------------------------------------


def test_wis2_watcher_downloads_bufr4_on_message(tmp_path: Path) -> None:
    """Watcher writes a .bufr4 file when a valid WIS2 notification arrives.

    The MQTT broker connection (``MQTTPubSubClient``) and the HTTP download
    (``requests.get``) are both mocked so no network access is required.
    """
    bufr4_filename = "test_observation.bufr4"
    fake_bufr4_content = b"\x00\x01\x02BUFR"  # minimal non-empty payload
    download_url = f"https://example.noaa.gov/data/{bufr4_filename}"

    # Build a fake requests.Response that streams the fake BUFR4 bytes.
    fake_response = MagicMock()
    fake_response.iter_content.return_value = [fake_bufr4_content]
    fake_response.raise_for_status.return_value = None

    # Override watcher's download directory to use pytest's tmp_path.
    watcher.DOWNLOAD_DIR = str(tmp_path)

    captured_callbacks: dict[str, object] = {}
    subscribed_topics: list[list[str]] = []

    class FakeMQTTPubSubClient:
        """Minimal stand-in for pywis_pubsub.mqtt.MQTTPubSubClient."""

        def __init__(self, broker_url: str) -> None:
            pass  # no network I/O

        def bind(self, event: str, callback: object) -> None:
            captured_callbacks[event] = callback

        def sub(self, topics: list[str]) -> None:
            subscribed_topics.append(topics)

    with (
        patch(
            "geode.ingest.watcher.MQTTPubSubClient",
            new=FakeMQTTPubSubClient,
        ),
        patch(
            "geode.ingest.watcher.requests.get",
            return_value=fake_response,
        ) as mock_get,
    ):
        watcher.run()

        # Verify the watcher registered an on_message handler.
        assert "on_message" in captured_callbacks, (
            "watcher.run() did not bind an 'on_message' callback"
        )

        # Verify the watcher subscribed to the expected topic.
        assert subscribed_topics, "watcher.run() did not call client.sub()"
        assert any(watcher.TOPIC in topics for topics in subscribed_topics), (
            f"Expected topic {watcher.TOPIC!r} not found in subscribed topics: {subscribed_topics}"
        )

        # Simulate a WIS2 notification arriving on the subscribed topic.
        fake_msg = types.SimpleNamespace(
            topic=watcher.TOPIC.rstrip("#"),
            payload=_make_fake_wis2_notification(download_url, bufr4_filename).encode(),
        )
        on_message = captured_callbacks["on_message"]
        on_message(client=None, userdata=None, msg=fake_msg)

    # Assert the file was downloaded and saved with the correct extension.
    downloaded_files = list(tmp_path.glob("*.bufr4"))
    assert len(downloaded_files) == 1, (
        f"Expected 1 .bufr4 file in {tmp_path}, found: {downloaded_files}"
    )
    assert downloaded_files[0].name == bufr4_filename
    assert downloaded_files[0].stat().st_size > 0


def test_wis2_watcher_ignores_non_bufr_links(tmp_path: Path) -> None:
    """Watcher does not download files when no canonical BUFR link is present.

    Parameters
    ----------
    tmp_path : Path
        Pytest fixture providing a temporary directory.
    """
    watcher.DOWNLOAD_DIR = str(tmp_path)

    captured_callbacks: dict[str, object] = {}

    class FakeMQTTPubSubClient:
        def __init__(self, broker_url: str) -> None:
            pass

        def bind(self, event: str, callback: object) -> None:
            captured_callbacks[event] = callback

        def sub(self, topics: list[str]) -> None:
            pass

    with patch("geode.ingest.watcher.MQTTPubSubClient", new=FakeMQTTPubSubClient):
        watcher.run()

    # Send a notification whose link is NOT application/bufr.
    non_bufr_payload = json.dumps(
        {
            "links": [
                {
                    "rel": "canonical",
                    "type": "application/json",
                    "href": "https://example.noaa.gov/data/file.json",
                }
            ]
        }
    )
    fake_msg = types.SimpleNamespace(
        topic=watcher.TOPIC.rstrip("#"),
        payload=non_bufr_payload.encode(),
    )
    on_message = captured_callbacks["on_message"]
    on_message(client=None, userdata=None, msg=fake_msg)

    assert list(tmp_path.iterdir()) == [], (
        "No files should be downloaded for non-BUFR notifications"
    )
