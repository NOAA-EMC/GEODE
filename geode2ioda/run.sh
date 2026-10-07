#!/bin/bash
set -e

export XDG_CONFIG_HOME="$PWD/config"
export PYTHONPATH="$PWD/build:$PWD"

python test_geode_to_osdf.py
