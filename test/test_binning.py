import numpy as np
import pytest
import xarray as xr

import geode
from geode.data.filter.superob import SuperobbingFilter
from geode.data.manager import data_manager


def _build_synthetic_atms_datatree():
    times = np.array(
        [
            "2021-07-31T22:44:00",
            "2021-07-31T22:44:10",
            "2021-07-31T22:44:20",
            "2021-07-31T22:44:30",
        ],
        dtype="datetime64[s]",
    )

    # First 3 points sit inside grid cell lat=[0, 1), lon=[0, 1.25) AND inside a single 3D voxel.
    # Point 1 (0.5, 0.625) is the exact center of the [0, 1) x [0, 1.25) grid cell.
    # Point 4 (10.2, 20.3) is isolated in its own cell/voxel.
    lats = np.array([0.48, 0.50, 0.51, 10.20], dtype=np.float64)
    lons = np.array([0.60, 0.625, 0.64, 20.30], dtype=np.float64)

    bt = np.array(
        [
            [200.0, 210.0],
            [210.0, 220.0],
            [290.0, 260.0],
            [300.0, 310.0],
        ],
        dtype=np.float32,
    )

    station_id = xr.DataArray(
        np.array([101, 102, 103, 2147483647], dtype=np.int32),
        dims=("Location",),
        attrs={"long_name": "Station identifier"},
    )
    station_id.encoding["_FillValue"] = np.int32(2147483647)

    return xr.DataTree.from_dict(
        {
            "/": xr.Dataset(
                coords={
                    "Location": np.arange(4, dtype=np.int32),
                    "Channel": np.array([1, 2], dtype=np.int32),
                }
            ),
            "/MetaData": xr.Dataset(
                {
                    "dateTime": ("Location", times),
                    "latitude": ("Location", lats),
                    "longitude": ("Location", lons),
                    "stationID": station_id,
                }
            ),
            "/ObsValue": xr.Dataset(
                {
                    "brightnessTemperature": (("Location", "Channel"), bt),
                }
            ),
        }
    )


def _put_synthetic_atms(name="atms_test"):
    data_manager.put(name, _build_synthetic_atms_datatree())
    return name


def test_grid_thinning_center(use_empty_data_lake):
    dataset = _put_synthetic_atms()

    result = geode.get(
        dataset,
        "2021-07-31T22:44:00",
        "2021-07-31T22:45:00",
        filters=[{"thinning": {"grid": [1.0, 1.25], "strategy": "center"}}],
    )

    lats = result["MetaData/latitude"].values[:]
    lons = result["MetaData/longitude"].values[:]
    bt = result["ObsValue/brightnessTemperature"].values[:]

    assert len(lats) == 2
    np.testing.assert_allclose(lats, [0.50, 10.20])
    np.testing.assert_allclose(lons, [0.625, 20.30])
    np.testing.assert_allclose(bt, [[210.0, 220.0], [300.0, 310.0]])


def test_grid_superobbing_mean_median_and_encoding(use_empty_data_lake):
    # 1. Verify direct in-memory encoding preservation on SuperobbingFilter
    raw_dt = _build_synthetic_atms_datatree()
    direct_out = SuperobbingFilter(
        {"grid": [1.0, 1.25], "aggregation": "mean", "min_obs": 2}
    ).apply(raw_dt)
    assert direct_out["MetaData/stationID"].encoding.get("_FillValue") == np.int32(
        2147483647
    )

    # 2. Verify end-to-end geode.get behavior (mean, median, dtypes, and Zarr _FillValue attr)
    dataset = _put_synthetic_atms()

    mean_res = geode.get(
        dataset,
        "2021-07-31T22:44:00",
        "2021-07-31T22:45:00",
        filters=[
            {"superobbing": {"grid": [1.0, 1.25], "aggregation": "mean", "min_obs": 2}}
        ],
    )

    lats = mean_res["MetaData/latitude"].values[:]
    bt_mean = mean_res["ObsValue/brightnessTemperature"].values[:]

    assert len(lats) == 1
    np.testing.assert_allclose(bt_mean[0], [700.0 / 3.0, 230.0], rtol=1e-5)
    assert mean_res["MetaData/stationID"].dtype == np.dtype("int32")
    assert mean_res["MetaData/stationID"].attrs.get("_FillValue") == 2147483647

    median_res = geode.get(
        dataset,
        "2021-07-31T22:44:00",
        "2021-07-31T22:45:00",
        filters=[
            {
                "superobbing": {
                    "grid": [1.0, 1.25],
                    "aggregation": "median",
                    "min_obs": 2,
                }
            }
        ],
    )
    np.testing.assert_allclose(
        median_res["ObsValue/brightnessTemperature"].values[:][0],
        [210.0, 220.0],
        rtol=1e-5,
    )


def test_superobbing_circular_longitude_and_polar_scaling(use_empty_data_lake):
    times = np.array(
        [
            "2021-07-31T22:44:00",
            "2021-07-31T22:44:10",
            "2021-07-31T22:44:20",
            "2021-07-31T22:44:30",
        ],
        dtype="datetime64[s]",
    )
    # Pair 1: both inside [359.0, 360.0) cell near 0/360 wrap (circular mean ~359.5, not 180)
    # Pair 2: at 80.5N, n_lon = round(360 * cos(80.5)) = 59 -> bin width = 6.102 deg,
    # so 7.0 and 11.5 (4.5 deg apart) fall inside the SAME polar bin [6.102, 12.203).
    lats = np.array([0.2, 0.3, 80.2, 80.3], dtype=np.float64)
    lons = np.array([359.2, 359.8, 7.0, 11.5], dtype=np.float64)
    bt = np.array([250.0, 260.0, 220.0, 230.0], dtype=np.float32)

    datatree = xr.DataTree.from_dict(
        {
            "/": xr.Dataset(coords={"Location": np.arange(4, dtype=np.int32)}),
            "/MetaData": xr.Dataset(
                {
                    "dateTime": ("Location", times),
                    "latitude": ("Location", lats),
                    "longitude": ("Location", lons),
                }
            ),
            "/ObsValue": xr.Dataset({"brightnessTemperature": ("Location", bt)}),
        }
    )
    data_manager.put("polar_wrap_test", datatree)

    result = geode.get(
        "polar_wrap_test",
        "2021-07-31T22:44:00",
        "2021-07-31T22:45:00",
        filters=[
            {"superobbing": {"grid": [1.0, 1.0], "aggregation": "mean", "min_obs": 2}}
        ],
    )

    out_lons = result["MetaData/longitude"].values[:]
    assert len(out_lons) == 2
    np.testing.assert_allclose(out_lons[0] % 360.0, 359.5, atol=1e-4)
    np.testing.assert_allclose(result["MetaData/latitude"].values[:], [0.25, 80.25])


def test_distance_superobbing_and_thinning(use_empty_data_lake):
    dataset = _put_synthetic_atms()

    superob_res = geode.get(
        dataset,
        "2021-07-31T22:44:00",
        "2021-07-31T22:45:00",
        filters=[
            {"superobbing": {"distance": 100.0, "aggregation": "mean", "min_obs": 2}}
        ],
    )
    assert len(superob_res["MetaData/latitude"].values[:]) == 1
    np.testing.assert_allclose(
        superob_res["ObsValue/brightnessTemperature"].values[:][0],
        [700.0 / 3.0, 230.0],
        rtol=1e-5,
    )

    thin_res = geode.get(
        dataset,
        "2021-07-31T22:44:00",
        "2021-07-31T22:45:00",
        filters=[{"thinning": {"distance": 100.0, "strategy": "center"}}],
    )
    assert len(thin_res["MetaData/latitude"].values[:]) == 2


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-v"]))
