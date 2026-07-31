import json
import os

import paho.mqtt.client as mqtt
import requests

# ==========================
# MQTT Client Configuration
# TODO: Move this externally to a config file
# or environment variables for better security and flexibility
# =========================
BROKER_ADDRESS = "wis2node.globaldata.nws.noaa.gov"
BROKER_PORT = 8883
TOPIC = "origin/a/wis2/us-noaa-nws/data/core/weather/#"
