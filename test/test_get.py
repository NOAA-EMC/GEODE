import datetime
import numpy as np
import matplotlib.pyplot as plt
import pytest
from importlib.resources import files

import geode
import geode.data.filter

def test_get(use_data_lake):
    result = geode.get("atms_n20", "2021-07-31T22:44:00", "2021-07-31T22:44:42")
    
    times = result["MetaData/dateTime"].values[:]
    
    assert len(times) > 0

    assert np.all(times >= np.datetime64("2021-07-31T22:44:00")) and \
           np.all(times <= np.datetime64("2021-07-31T22:44:42"))

    assert result is not None


def test_get_with_bounding_box(use_data_lake):
    min_lat = 30.0
    max_lat = 32.0
    min_lon = -180.0
    max_lon = 180.0

    result = geode.get(
        "atms_n20", 
        "2021-07-31T22:44:00",
        "2021-07-31T22:44:42",
        filters=[{"bounding_box": {
            "min_lat": min_lat,
            "max_lat": max_lat,
            "min_lon": min_lon,
            "max_lon": max_lon
    }}])

    assert result is not None

    lats = result["MetaData/latitude"].values[:]
    lons = result["MetaData/longitude"].values[:]

    assert len(lats) > 0
    assert len(lons) > 0

    assert np.all(lats >= min_lat) and np.all(lats <= max_lat)
    assert np.all(lons >= min_lon) and np.all(lons <= max_lon)


def test_get_with_geojson(use_data_lake):
    geojson = {
        "type": "Polygon",
        "coordinates": [
            [
                [-180.0, 30.0],
                [-180.0, 32.0],
                [180.0, 32.0],
                [180.0, 30.0],
                [-180.0, 30.0]
            ]
        ]
    }

    result = geode.get(
        "atms_n20",
        "2021-07-31T22:44:00",
        "2021-07-31T22:44:42",
        filters=[{"geojson": geojson}]
    )

    assert result is not None

    lats = result["MetaData/latitude"].values[:]
    lons = result["MetaData/longitude"].values[:]

    assert len(lats) > 0
    assert len(lons) > 0

    assert np.all(lats >= 30.0) and np.all(lats <= 32.0)
    assert np.all(lons >= -180.0) and np.all(lons <= 180.0)


def test_get_with_geojson_path(use_data_lake):
    geojson_path = (
        files(geode.data.filter) / "regions" / "central_pacific_basin.geojson"
    )

    result = geode.get(
        "atms_n20",
        "2021-07-31T22:44:00",
        "2021-07-31T22:44:42",
        filters=[{"geojson": str(geojson_path)}]
    )

    assert result is not None

    lats = result["MetaData/latitude"].values[:]
    lons = result["MetaData/longitude"].values[:]

    assert len(lats) > 0
    assert len(lons) > 0

    assert np.all(lats >= 20.0) and np.all(lats <= 40.0)
    assert np.all(lons >= -180.0) and np.all(lons <= -100.0)


def test_get_region(use_data_lake):

    result = geode.get("atms_n20", 
                       "2021-07-30T00:00:00",
                       "2021-07-31T23:59:59",
                       filters=[{"region": "central_pacific_basin"}]
    )

    assert result is not None

    lats = result["MetaData/latitude"].values[:]
    lons = result["MetaData/longitude"].values[:]

    assert len(lats) > 0
    assert len(lons) > 0

    assert np.all(lats >= 20.0) and np.all(lats <= 40.0)
    assert np.all(lons >= -180.0) and np.all(lons <= -100.0)


def test_get_combined(use_data_lake):
    result = geode.get("atms_n20", 
                       "2021-07-30T00:00:00",
                       "2021-07-31T23:59:59",
                       filters=[{"region": "central_pacific_basin"},
                                {"bounding_box": {
                                    "min_lat": -90.0,
                                    "max_lat": -60.0,
                                    "min_lon": -180.0,
                                    "max_lon": -75.0
                                }}]
    )

    assert result is not None

    lats = result["MetaData/latitude"].values[:]
    lons = result["MetaData/longitude"].values[:]

    assert len(lats) > 0
    assert len(lons) > 0

    assert np.all(lats >= -90.0) and np.all(lats <= 40.0)
    assert np.all(lons >= -180.0) and np.all(lons <= -75.0)

if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-v"]))
