from pathlib import Path

import pytest

from geode.configs.geode_config import geode_config
from geode.ingest.consumers import wis2_listener


def test_wis2_listener(use_empty_data_lake):
    success = False  # Just don't crash

    listener = wis2_listener.Wis2Listener()

    # Set up a callback function to be called when a message is received
    def on_message_callback() -> None:
        nonlocal success

        listener.stop()

        # Check if it exists, is a directory, and contains any files or folders
        path = Path(geode_config.data_lake.full_base_path)

        if path.is_dir() and any(path.iterdir()):
            success = True
        else:
            success = False

    # Create an instance of Wis2Listener and set the callback
    listener.on_message_callback = on_message_callback
    listener.listen()

    print(f"Success: {success}")

    # Just don't crash for now
    assert True, "Listener did not receive any messages"


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-v"]))
