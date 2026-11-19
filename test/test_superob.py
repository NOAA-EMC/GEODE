import numpy as np
import pytest
import xarray as xr

from geode.data.filter.superob import SuperobbingFilter
from geode.data.keys import LatitudeKey, LocationKey, LongitudeKey

try:
    from geode.data.keys import DatetimeKey as DateTimeKey
except ImportError:
    DateTimeKey = "MetaData/dateTime"


def _make_datatree(
    lats: list[float],
    lons: list[float],
    lon_dtype: np.dtype = np.float64,
) -> xr.DataTree:
    """Build a minimal GEODE DataTree with MetaData and ObsValue groups."""
    n = len(lats)
    lat_group, lat_name = LatitudeKey.split("/", 1)
    lon_group, lon_name = LongitudeKey.split("/", 1)
    dt_group, dt_name = DateTimeKey.split("/", 1)

    assert lat_group == lon_group == dt_group
    meta_ds = xr.Dataset(
        {
            lat_name: (LocationKey, np.asarray(lats, dtype=np.float64)),
            lon_name: (LocationKey, np.asarray(lons, dtype=lon_dtype)),
            dt_name: (
                LocationKey,
                np.arange(
                    np.datetime64("2026-01-01T00:00:00"),
                    np.datetime64("2026-01-01T00:00:00") + np.timedelta64(n, "s"),
                    np.timedelta64(1, "s"),
                ),
            ),
        }
    )
    obs_ds = xr.Dataset(
        {"temperature": (LocationKey, np.full(n, 280.0, dtype=np.float64))}
    )
    return xr.DataTree.from_dict({lat_group: meta_ds, "ObsValue": obs_ds})


@pytest.mark.parametrize(
    "mode_cfg",
    [
        {"distance": 50.0},
        # Odd n_lon (=359 at equator) so a single grid cell straddles ±180°
        {"grid": 360.0 / 359.0},
    ],
)
@pytest.mark.parametrize("aggregation", ["mean", "median"])
@pytest.mark.parametrize("lon_dtype", [np.float64, np.float32])
@pytest.mark.parametrize(
    ("input_lons", "expected_lon", "expected_range"),
    [
        # Antimeridian symmetric in [-180, 180): must be -180, NOT 0
        ([179.9, -179.9], -180.0, (-180.0, 180.0)),
        # Antimeridian asymmetric in [-180, 180)
        ([179.8, -179.9], 179.95, (-180.0, 180.0)),
        ([179.9, -179.8], -179.95, (-180.0, 180.0)),
        # Exact antimeridian endpoints
        ([-180.0, -180.0], -180.0, (-180.0, 180.0)),
        ([180.0, 180.0], 180.0, (0.0, 360.0)),
        # Antimeridian in [0, 360)
        ([179.9, 180.1], 180.0, (0.0, 360.0)),
    ],
)
def test_superob_longitude_wrapping_near_antimeridian(
    mode_cfg: dict,
    aggregation: str,
    lon_dtype: np.dtype,
    input_lons: list[float],
    expected_lon: float,
    expected_range: tuple[float, float],
) -> None:
    dt = _make_datatree(lats=[0.0, 0.0], lons=input_lons, lon_dtype=lon_dtype)
    filt = SuperobbingFilter({**mode_cfg, "aggregation": aggregation})

    out_dt = filt.apply(dt)
    out_lons = np.asarray(out_dt[LongitudeKey].variable.values)

    assert out_lons.shape == (1,)
    lo, hi = expected_range
    assert lo <= out_lons[0] < hi

    angular_diff = ((float(out_lons[0]) - expected_lon + 180.0) % 360.0) - 180.0
    assert abs(angular_diff) < 1e-4


@pytest.mark.parametrize("aggregation", ["mean", "median"])
@pytest.mark.parametrize("lon_dtype", [np.float64, np.float32])
@pytest.mark.parametrize(
    ("input_lons", "expected_lon"),
    [
        # Prime meridian wrap in [0, 360): must be 0 (never 180 or 360.0)
        ([359.9, 0.1], 0.0),
        ([359.8, 0.1], 359.95),
    ],
)
def test_superob_longitude_wrapping_near_prime_meridian(
    aggregation: str,
    lon_dtype: np.dtype,
    input_lons: list[float],
    expected_lon: float,
) -> None:
    dt = _make_datatree(lats=[0.0, 0.0], lons=input_lons, lon_dtype=lon_dtype)
    filt = SuperobbingFilter({"distance": 50.0, "aggregation": aggregation})

    out_dt = filt.apply(dt)
    out_lons = np.asarray(out_dt[LongitudeKey].variable.values)

    assert out_lons.shape == (1,)
    assert 0.0 <= out_lons[0] < 360.0

    angular_diff = ((float(out_lons[0]) - expected_lon + 180.0) % 360.0) - 180.0
    assert abs(angular_diff) < 1e-4


def test_superob_reduced_grid_polar_cell_straddling_antimeridian() -> None:
    """At lat=89.5° with dlon=1.0°, n_lon=3 so cell 1 [120°, 240°) straddles ±180°."""
    dt = _make_datatree(lats=[89.5, 89.5], lons=[179.9, -179.9])
    filt = SuperobbingFilter({"grid": 1.0, "aggregation": "mean"})

    out_dt = filt.apply(dt)
    out_lons = np.asarray(out_dt[LongitudeKey].variable.values)

    assert out_lons.shape == (1,)
    np.testing.assert_allclose(out_lons, [-180.0], atol=1e-6)


def test_superob_multiple_clusters_across_dateline_and_prime_meridian() -> None:
    """Verify per-cluster unwrapping does not bleed across multiple clusters."""
    lats = [0.0, 0.0, 10.0, 10.0, -20.0, -20.0]
    lons = [179.9, -179.9, -0.1, 0.1, 45.0, 45.2]
    dt = _make_datatree(lats=lats, lons=lons)

    filt = SuperobbingFilter({"distance": 50.0, "aggregation": "mean"})
    out_dt = filt.apply(dt)
    out_lons = np.asarray(out_dt[LongitudeKey].variable.values)

    np.testing.assert_allclose(out_lons, [-180.0, 0.0, 45.1], atol=1e-6)
