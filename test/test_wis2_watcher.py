import os
import sys
import time

import paho.mqtt.client as mqtt

sys.path.append(
    os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "src")
)  # Add src/ to sys.path

from geode.ingest import watcher

# ==========================
# MQTT Client Configuration
# TODO: Move this externally to a config file
# or environment variables for better security and flexibility
# =========================
BROKER_ADDRESS = "wis2node.globaldata.nws.noaa.gov"
BROKER_PORT = 8883

# ==========================================
# Main Execution
# ==========================================
if __name__ == "__main__":
    client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)

    # Add the WIS2 public credentials here
    client.username_pw_set("everyone", "everyone")

    # Enable TLS/SSL (Crucial for port 8883)
    # Calling this without arguments uses the system's default trusted certificate authorities, 
    # which will perfectly validate the .gov domain.
    client.tls_set()

    client.on_connect = watcher.on_connect
    client.on_message = watcher.on_message

    print(f"[*] Connecting to {BROKER_ADDRESS} with TLS...")
    client.connect(BROKER_ADDRESS, BROKER_PORT, keepalive=60)

    client.loop_start()
    try:
        print("[*] Running listener for 60 seconds (Ctrl+C to exit early)...")
        start_time = time.time()
        while time.time() - start_time < 60:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\n[*] Keyboard interrupt detected.")
    finally:
        print("[*] Stopping loop and disconnecting...")
        client.loop_stop()
        client.disconnect()
