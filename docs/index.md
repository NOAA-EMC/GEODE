# GEODE

GEODE is a geospatial Earth observation data engine for ingesting, organizing, and retrieving observation data from WIS2 and related data sources.

## Overview

This project provides:

- a catalog of data lake configuration options
- ingestion workflows for BUFR-based observations
- MQTT-based WIS2 listener support
- data retrieval utilities backed by Zarr, Icechunk, or NetCDF storage

## API documentation

The API reference is organized by functional area:

- [Core API](api/core.md)
- [Configuration](api/configuration.md)
- [Data Access](api/data.md)
- [Ingest & Listeners](api/ingest.md)
- [Models](api/models.md)
