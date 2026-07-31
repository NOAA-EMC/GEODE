import json
import os

import requests

# ==========================
# MQTT Client Configuration
# TODO: Move this externally to a config file
# or environment variables for better security and flexibility
# =========================
BROKER_ADDRESS = "wis2node.globaldata.nws.noaa.gov"
BROKER_PORT = 8883
TOPIC = "origin/a/wis2/us-noaa-nws/data/core/weather/#"
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
        
        with open(filepath, 'wb') as f:
            for chunk in response.iter_content(chunk_size=8192):
                f.write(chunk)
                
        print(f"[+] Successfully saved to: {filepath}")
        
    except requests.exceptions.RequestException as e:
        print(f"[-] Network error downloading {url}: {e}")
    except Exception as e:
        print(f"[-] Error saving file: {e}")

# ==========================================
# MQTT Callbacks
# ==========================================
def on_connect(client, userdata, flags, reason_code, properties):
    """Fired when the client successfully connects to the broker."""
    if reason_code == 0:
        print(f"[+] Connected to MQTT broker at {BROKER_ADDRESS}:{BROKER_PORT}")
        client.subscribe(TOPIC)
        print(f"[*] Subscribed to topic: {TOPIC}")
    else:
        print(f"[-] Connection failed with code {reason_code}")

def on_message(client, userdata, msg):
    """Fired when a new message is published to the subscribed topic."""
    # Double-check that we are only processing messages from our target topic tree
    # (Helpful if you add more subscriptions later)
    if not msg.topic.startswith(TOPIC[:-2]):  # Remove the trailing '#' for prefix matching
        return

    payload_str = msg.payload.decode('utf-8')
    print(f"\n[*] Notification received on {msg.topic}")
    
    try:
        data = json.loads(payload_str)
        url = None
        filename = None
        
        # Parse standard WIS2 Notification Message (GeoJSON)
        # The download link is typically found in the 'links' array
        if "links" in data:
            for link in data.get("links", []):
                # Look for the actual data payload URL (often marked as canonical or just having an href)
                if "href" in link:
                    url = link["href"]
                    # WIS2 payloads rarely provide a explicit local "filename" field, 
                    # so we extract the file name directly from the end of the URL
                    filename = url.split("/")[-1]
                    
                    # Stop at the first valid link found
                    break 

        # Fallback for the older simple schema, just in case
        if not url:
            url = data.get("url")
            filename = data.get("filename")
        
        if url and filename:
            download_file(url, filename)
        else:
            print("[-] Could not find a valid download URL in the payload.")
            print(f"    Payload excerpt: {payload_str[:200]}...") # Print first 200 chars for debugging
            
    except json.JSONDecodeError:
        print("[-] Invalid payload format: Message must be valid JSON")

