import os, sys
from datetime import datetime, timezone

sys.path.append(
    os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'src'))
)

import xarray as xr

import geode

def test_get():
    start_time = datetime(2026, 8, 20, 0, 0, 0, tzinfo=timezone.utc)
    end_time = datetime(2026, 8, 20, 0, 0, 0, tzinfo=timezone.utc)
    result = geode.get('synop', start_time, end_time)

    # print (result)

    assert isinstance(result, xr.DataTree)


    result = geode.get('synop', start_time, end_time, vars=['ObsValue/temperature'])

    # print (result)

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
