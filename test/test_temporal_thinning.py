"""Unit tests for TemporalThinningFilter."""

import numpy as np
import pytest
import xarray as xr

from geode.data.filter.base import ValidationError
from geode.data.filter.temporal_thinning import TemporalThinningFilter
from geode.data.keys import IsSortedFlag, LocationKey, TimeKey


def _make_datatree(
    times: np.ndarray,
    *,
    is_sorted: bool = True,
    time_key: str = TimeKey,
) -> xr.DataTree:
    """Build a minimal GEODE DataTree with MetaData, ObsValue, and a static group."""
    n = len(times)
    time_group, time_name = time_key.split("/", 1)
    meta_ds = xr.Dataset(
        {
            time_name: (LocationKey, times),
            "latitude": (LocationKey, np.linspace(-30.0, 30.0, n)),
        }
    )
    obs_ds = xr.Dataset(
        {"temperature": (LocationKey, np.arange(n, dtype=np.float64))}
    )
    static_ds = xr.Dataset({"version": xr.DataArray(1)})

    dt = xr.DataTree.from_dict(
        {time_group: meta_ds, "ObsValue": obs_ds, "MetaDataStatic": static_ds}
    )
    dt.attrs[IsSortedFlag] = is_sorted
    return dt


@pytest.mark.parametrize(
    "filter_cfg",
    [
        {"interval": np.timedelta64(1, "h")},
        {"interval": "1h"},
        {"interval": 3600},
        {"interval": 60, "units": "m"},
    ],
)
def test_temporal_thinning_1min_to_hourly_centered_on_hour(
    filter_cfg: dict,
) -> None:
    """1-minute data thinned to hourly retains exact observations on the hour."""
    times = np.arange(
        np.datetime64("2026-01-01T00:00:00", "us"),
        np.datetime64("2026-01-01T03:01:00", "us"),
        np.timedelta64(1, "m"),
    )
    dt = _make_datatree(times, is_sorted=True)

    filt = TemporalThinningFilter(filter_cfg)
    out_dt = filt.apply(dt)

    expected = np.array(
        [
            "2026-01-01T00:00:00",
            "2026-01-01T01:00:00",
            "2026-01-01T02:00:00",
            "2026-01-01T03:00:00",
        ],
        dtype="datetime64[us]",
    )
    np.testing.assert_array_equal(out_dt[TimeKey].variable.values, expected)
    assert out_dt["ObsValue"]["temperature"].sizes[LocationKey] == 4
    assert int(out_dt["MetaDataStatic"]["version"].values) == 1
    assert out_dt.attrs[IsSortedFlag] is True


def test_temporal_thinning_irregular_timestamps_nearest_to_hour() -> None:
    """Observations at 00:58 and 01:01 both fall in the 01:00 bin; 01:01 wins."""
    times = np.array(
        [
            "2026-01-01T00:58:00",
            "2026-01-01T01:01:00",
            "2026-01-01T01:29:00",
            "2026-01-01T01:31:00",
        ],
        dtype="datetime64[us]",
    )
    dt = _make_datatree(times)

    filt = TemporalThinningFilter({"interval": "1h", "strategy": "center"})
    out_dt = filt.apply(dt)

    expected = np.array(
        ["2026-01-01T01:01:00", "2026-01-01T01:31:00"],
        dtype="datetime64[us]",
    )
    np.testing.assert_array_equal(out_dt[TimeKey].variable.values, expected)


@pytest.mark.parametrize(
    ("strategy", "expected_ts"),
    [
        ("center", "2026-01-01T00:31:00"),
        ("first", "2026-01-01T00:05:00"),
        ("last", "2026-01-01T00:55:00"),
    ],
)
def test_temporal_thinning_interval_align_start_and_strategies(
    strategy: str,
    expected_ts: str,
) -> None:
    """With align='start', [00:00, 01:00) is centered at 00:30 and honors strategy."""
    times = np.array(
        [
            "2026-01-01T00:55:00",
            "2026-01-01T00:31:00",
            "2026-01-01T00:05:00",
        ],
        dtype="datetime64[us]",
    )
    dt = _make_datatree(times, is_sorted=False)

    filt = TemporalThinningFilter(
        {"interval": "1h", "align": "start", "strategy": strategy}
    )
    out_dt = filt.apply(dt)

    expected = np.array([expected_ts], dtype="datetime64[us]")
    np.testing.assert_array_equal(out_dt[TimeKey].variable.values, expected)
    assert out_dt.attrs[IsSortedFlag] is False


def test_temporal_thinning_interval_random_is_deterministic() -> None:
    # [00:00, 02:55] spans 4 centered hourly bins: 00:00, 01:00, 02:00, and 03:00
    times = np.arange(
        np.datetime64("2026-01-01T00:00:00", "us"),
        np.datetime64("2026-01-01T03:00:00", "us"),
        np.timedelta64(5, "m"),
    )
    dt = _make_datatree(times)

    filt_a = TemporalThinningFilter({"interval": "1h", "strategy": "random", "seed": 7})
    filt_b = TemporalThinningFilter({"interval": "1h", "strategy": "random", "seed": 7})

    out_a = filt_a.apply(dt)[TimeKey].variable.values
    out_b = filt_b.apply(dt)[TimeKey].variable.values
    assert len(out_a) == 4
    np.testing.assert_array_equal(out_a, out_b)


def test_temporal_thinning_custom_reference_time() -> None:
    """Anchoring reference_time at :30:00 creates bins [00:00,01:00), [01:00,02:00), [02:00,03:00)."""
    times = np.array(
        [
            "2026-01-01T00:00:00",
            "2026-01-01T00:29:00",
            "2026-01-01T01:32:00",
            "2026-01-01T02:00:00",
        ],
        dtype="datetime64[us]",
    )
    dt = _make_datatree(times)

    filt = TemporalThinningFilter(
        {
            "interval": "1h",
            "strategy": "center",
            "reference_time": "2026-01-01T00:30:00Z",
        }
    )
    out_dt = filt.apply(dt)

    expected = np.array(
        [
            "2026-01-01T00:29:00",
            "2026-01-01T01:32:00",
            "2026-01-01T02:00:00",
        ],
        dtype="datetime64[us]",
    )
    np.testing.assert_array_equal(out_dt[TimeKey].variable.values, expected)


def test_temporal_thinning_min_spacing_center_enforces_gap_across_boundaries() -> None:
    """min_spacing with strategy='center' picks :00 anchors first and blocks neighbors."""
    times = np.array(
        [
            "2026-01-01T00:50:00",  # 10 min from 01:00 -> blocked once 01:00 is chosen
            "2026-01-01T01:00:00",  # exact anchor -> chosen first
            "2026-01-01T01:40:00",  # 40 min after 01:00 -> blocked (< 1h)
            "2026-01-01T02:05:00",  # 65 min after 01:00 -> chosen
        ],
        dtype="datetime64[us]",
    )
    dt = _make_datatree(times)

    filt = TemporalThinningFilter({"min_spacing": 1, "units": "h", "strategy": "center"})
    out_dt = filt.apply(dt)

    expected = np.array(
        ["2026-01-01T01:00:00", "2026-01-01T02:05:00"],
        dtype="datetime64[us]",
    )
    np.testing.assert_array_equal(out_dt[TimeKey].variable.values, expected)


def test_temporal_thinning_min_spacing_first_and_last_preserve_input_order() -> None:
    times = np.array(
        [
            "2026-01-01T01:00:00",
            "NaT",
            "2026-01-01T00:00:00",
            "2026-01-01T00:30:00",
            "2026-01-01T02:05:00",
        ],
        dtype="datetime64[us]",
    )
    dt = _make_datatree(times, is_sorted=False)

    out_first = TemporalThinningFilter(
        {"min_spacing": "1h", "strategy": "first"}
    ).apply(dt)
    np.testing.assert_array_equal(
        out_first[TimeKey].variable.values,
        np.array(
            [
                "2026-01-01T01:00:00",
                "2026-01-01T00:00:00",
                "2026-01-01T02:05:00",
            ],
            dtype="datetime64[us]",
        ),
    )
    assert out_first.attrs[IsSortedFlag] is False

    out_last = TemporalThinningFilter(
        {"min_spacing": "1h", "strategy": "last"}
    ).apply(dt)
    np.testing.assert_array_equal(
        out_last[TimeKey].variable.values,
        np.array(
            [
                "2026-01-01T01:00:00",
                "2026-01-01T00:00:00",
                "2026-01-01T02:05:00",
            ],
            dtype="datetime64[us]",
        ),
    )


def test_temporal_thinning_all_nat_and_custom_time_key() -> None:
    nat_times = np.array(["NaT", "NaT"], dtype="datetime64[us]")
    dt_nat = _make_datatree(nat_times, is_sorted=True)
    out_nat = TemporalThinningFilter({"interval": "1h"}).apply(dt_nat)
    assert out_nat[TimeKey].sizes[LocationKey] == 0
    assert out_nat.attrs[IsSortedFlag] is True

    custom_key = "MetaData/customTime"
    times = np.array(
        ["2026-01-01T00:00:00", "2026-01-01T00:10:00", "2026-01-01T01:00:00"],
        dtype="datetime64[us]",
    )
    dt_custom = _make_datatree(times, time_key=custom_key)
    out_custom = TemporalThinningFilter(
        {"interval": "1h", "time_key": custom_key}
    ).apply(dt_custom)
    np.testing.assert_array_equal(
        out_custom[custom_key].variable.values,
        np.array(["2026-01-01T00:00:00", "2026-01-01T01:00:00"], dtype="datetime64[us]"),
    )


@pytest.mark.parametrize(
    "bad_cfg",
    [
        {},
        {"interval": "1h", "min_spacing": "1h"},
        {"interval": 0},
        {"interval": -60},
        {"interval": float("nan")},
        {"interval": True},
        {"interval": "not-a-duration"},
        {"min_spacing": -10},
        {"interval": "1h", "reference_time": "not-a-timestamp"},
        {"interval": "1h", "reference_time": True},
        {"interval": "1h", "strategy": "median"},
        {"interval": "1h", "align": "end"},
    ],
)
def test_temporal_thinning_validation_errors(bad_cfg: dict) -> None:
    with pytest.raises(ValidationError):
        TemporalThinningFilter(bad_cfg)
