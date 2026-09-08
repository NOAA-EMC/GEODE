import shutil
from pathlib import Path

import pytest

from geode.configs.geode_config import geode_config
from geode.ingest.consumers import wis2_listener


@pytest.fixture()
def cleanup():
    shutil.rmtree(geode_config.data_lake.full_base_path, ignore_errors=True)
    shutil.rmtree(geode_config.wis2.full_download_dir, ignore_errors=True)


def test_wis2_listener(cleanup):
    success = True  # Just don't crash

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

    assert success, "Listener did not receive any messages"


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-v"]))
