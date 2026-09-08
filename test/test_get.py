import datetime

import xarray as xr

import geode


def test_get():
    start_time = datetime.datetime(2026, 8, 20, 0, 0, 0, tzinfo=datetime.UTC)
    end_time = datetime.datetime(2026, 8, 20, 0, 0, 0, tzinfo=datetime.UTC)
    result = geode.get("synop", start_time, end_time)

    assert isinstance(result, xr.DataTree)

    result = geode.get("synop", start_time, end_time, vars=["ObsValue/temperature"])

    assert isinstance(result, xr.DataTree)

    # result = geode.get('synop', start_time, end_time, {'variables': ['temperature'],
    #                                                    'latitude': [30, 40],
    #                                                    'longitude': [-90, -80]})

    # result = geode.get('synop', start_time, end_time, {'variables': ['temperature'],
    #                                                    'latitude': [30, 40],
    #                                                    'longitude': [-90, -80]})

    assert isinstance(result, xr.DataTree)


if __name__ == "__main__":
    test_get()
    print("Test passed.")
