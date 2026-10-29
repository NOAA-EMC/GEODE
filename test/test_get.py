from importlib.resources import files

import numpy as np
import pytest

import geode
import geode.data.filter


def test_get(use_data_lake):
    result = geode.get("globe", "2021-07-31T22:44:00", "2021-07-31T22:44:42")

    assert result is not None

    times = result["MetaData/dateTime"].values[:]

    assert len(times) > 0

    assert np.all(times >= np.datetime64("2021-07-31T22:44:00")) and np.all(
        times < np.datetime64("2021-07-31T22:44:42")
    )


def test_get_time_bounds(use_data_lake):
    result = geode.get("stripe", "2021-07-31T22:44:00", "2021-07-31T22:45:00")

    times = result["MetaData/dateTime"].values[:]

    assert (np.min(times) == np.datetime64("2021-07-31T22:44:00")) and (
        np.max(times) == np.datetime64("2021-07-31T22:44:00")
    )

    result = geode.get("stripe", "2021-07-31T22:44:00", "2021-07-31T22:45:01")

    times = result["MetaData/dateTime"].values[:]

    assert (np.min(times) == np.datetime64("2021-07-31T22:44:00")) and (
        np.max(times) == np.datetime64("2021-07-31T22:45:00")
    )


def test_get_with_bounding_box(use_data_lake):
    min_lat = 30.0
    max_lat = 32.0
    min_lon = -180.0
    max_lon = 180.0

    result = geode.get(
        "globe",
        "2021-07-31T22:44:00",
        "2021-07-31T22:44:42",
        filters=[
            {
                "bounding_box": {
                    "min_lat": min_lat,
                    "max_lat": max_lat,
                    "min_lon": min_lon,
                    "max_lon": max_lon,
                }
            }
        ],
    )

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
                [-180.0, 30.0],
            ]
        ],
    }

    result = geode.get(
        "globe",
        "2021-07-31T22:44:00",
        "2021-07-31T22:44:42",
        filters=[{"geojson": geojson}],
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
        "globe",
        "2021-07-30T00:00:00",
        "2021-07-31T23:59:59",
        filters=[{"geojson": str(geojson_path)}],
    )

    assert result is not None

    lats = result["MetaData/latitude"].values[:]
    lons = result["MetaData/longitude"].values[:]

    assert len(lats) > 0
    assert len(lons) > 0

    assert np.all(lats >= 0.0) and np.all(lats <= 40.0)
    assert np.all(lons >= -180.0) and np.all(lons <= -140.0)


def test_get_region(use_data_lake):

    result = geode.get(
        "globe",
        "2021-07-30T00:00:00",
        "2021-07-31T23:59:59",
        filters=[{"region": "central_pacific_basin"}],
    )

    assert result is not None

    lats = result["MetaData/latitude"].values[:]
    lons = result["MetaData/longitude"].values[:]

    assert len(lats) > 0
    assert len(lons) > 0

    assert np.all(lats >= 0.0) and np.all(lats <= 40.0)
    assert np.all(lons >= -180.0) and np.all(lons <= -140.0)


def test_get_region_w_border(use_data_lake):

    result = geode.get(
        "globe",
        "2021-07-30T00:00:00",
        "2021-07-31T23:59:59",
        filters=[
            {"region": {"name": "central_pacific_basin", "border_width": 180}}
        ],  # huge border
    )

    assert result is not None

    lats = result["MetaData/latitude"].values[:]
    lons = result["MetaData/longitude"].values[:]

    assert len(lats) > 0
    assert len(lons) > 0

    # make sure we captured something outside the original region
    assert np.any(lons >= -75.0)


def test_get_combined(use_data_lake):
    result = geode.get(
        "globe",
        "2021-07-30T00:00:00",
        "2021-07-31T23:59:59",
        filters=[
            {"region": "central_pacific_basin"},
            {
                "bounding_box": {
                    "min_lat": -90.0,
                    "max_lat": -60.0,
                    "min_lon": -180.0,
                    "max_lon": -75.0,
                }
            },
        ],
    )

    assert result is not None

    lats = result["MetaData/latitude"].values[:]
    lons = result["MetaData/longitude"].values[:]

    assert len(lats) > 0
    assert len(lons) > 0

    in_region = (lats >= 0.0) & (lats <= 40.0) & (lons <= -140.0)
    in_box = (lats >= -90.0) & (lats <= -60.0) & (lons <= -75.0)
    assert np.all(in_region | in_box)
    assert np.any(in_region) and np.any(in_box)


def test_get_w_channels(use_data_lake):

    result = geode.get(
        "globe",
        "2021-07-30T00:00:00",
        "2021-07-31T23:59:59",
        filters=[{"channels": [1, 2]}],
    )

    assert result is not None

    channels = result["Channel"].values[:]
    np.testing.assert_array_equal(channels, [1, 2])
    assert result["ObsValue/brightnessTemperature"].sizes["Channel"] == 2

    # Test when no Channels coordinate in data
    with pytest.warns(Warning):
        result = geode.get(
            "stripe",
            "2021-07-30T00:00:00",
            "2021-07-31T23:59:59",
            filters=[{"channels": [1, 2]}],
        )

    assert result is not None
    assert len(result["ObsValue/temperature"]) > 0


def test_get_w_vars(use_data_lake):

    result = geode.get(
        "globe",
        "2021-07-30T00:00:00",
        "2021-07-31T23:59:59",
        filters=[{"variables": ["ObsValue/brightnessTemperature"]}],
    )

    assert result is not None

    assert set(result["/"].coords) == {"Location", "Channel"}
    assert set(result["ObsValue"].data_vars) == {"brightnessTemperature"}
    assert set(result["MetaData"].data_vars) == {
        "dateTime",
        "latitude",
        "longitude",
    }


def test_get_periodic(use_data_lake):
    """Periodic windows include both their start and end timestamps."""
    period_hours = 3
    window_hours = 1

    result = geode.get(
        "stripe",
        "2021-07-30T00:00:00",
        "2021-07-31T23:59:59",
        filters=[{"periodic": {"period": period_hours, "window": window_hours}}],
    )

    unfiltered = geode.get(
        "stripe",
        "2021-07-30T00:00:00",
        "2021-07-31T23:59:59",
    )

    times = unfiltered["MetaData/dateTime"].values
    assert times.size > 0
    offsets = times - times[0]
    expected_times = times[
        offsets % np.timedelta64(period_hours, "h") <= np.timedelta64(window_hours, "h")
    ]
    np.testing.assert_array_equal(
        result["MetaData/dateTime"].values,
        expected_times,
    )


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-v"]))
