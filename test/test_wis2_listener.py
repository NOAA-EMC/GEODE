import os
import sys
import shutil
import threading
import time
from pathlib import Path

sys.path.append(
    os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "src")
)  # Add src/ to sys.path

from geode.ingest.listeners import wis2_listener
from geode.configs.geode_config import geode_config


def test_wis2_listener():
    success = False

    listener = wis2_listener.Wis2Listener()

    test_data_dir = os.path.join(geode_config.root_dir, "test")
    geode_config.data_lake.base_dir = test_data_dir

    if os.path.exists(test_data_dir):
        shutil.rmtree(test_data_dir)  # Clean up the test directory if it exists

    # Set up a callback function to be called when a message is received
    def on_message_callback() -> None:
        nonlocal success

        listener.stop()

        # Check if it exists, is a directory, and contains any files or folders
        path = Path(test_data_dir)

        if path.is_dir() and any(path.iterdir()):
            success = True
        else:
            success = False
        
        shutil.rmtree(test_data_dir)  # Clean up the test directory

    # Create an instance of Wis2Listener and set the callback
    listener.on_message_callback = on_message_callback
    listener.listen()

    assert success, "Listener did not receive any messages"


if __name__ == "__main__":
    test_wis2_listener()
