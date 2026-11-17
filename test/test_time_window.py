import numpy as np
import xarray as xr

from geode.data.filter.time_window import TimeWindowFilter
from geode.data.keys import IsSortedFlag


def test_time_window_unsorted():
    times = np.array(
        [
            "2026-09-13T10:00:00",
            "2026-09-13T05:30:00",
            "2026-09-13T02:00:00",
            "2026-09-13T06:00:00",
            "NaT",
        ],
        dtype="datetime64[ns]",
    )
    values = np.array([10, 20, 30, 40, 50])

    tree = xr.DataTree.from_dict(
        {
            "/": xr.Dataset(
                coords={"Location": np.arange(len(times))},
                attrs={IsSortedFlag: False},
            ),
            "/MetaData": xr.Dataset({"dateTime": ("Location", times)}),
            "/ObsValue": xr.Dataset({"value": ("Location", values)}),
        }
    )

    result = TimeWindowFilter(
        {
            "start_time": np.datetime64("2026-09-13T03:00:00"),
            "end_time": np.datetime64("2026-09-13T09:00:00"),
        }
    ).apply(tree)

    np.testing.assert_array_equal(
        result["MetaData/dateTime"].values,
        times[[1, 3]],
    )
    np.testing.assert_array_equal(
        result["ObsValue/value"].values,
        values[[1, 3]],
    )
