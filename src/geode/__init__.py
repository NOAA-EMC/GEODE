from __future__ import annotations

from datetime import datetime

import xarray as xr

__all__ = ["get"]


def get(
    data_type: str,
    start_time: datetime | str,
    end_time: datetime | str,
    vars: list[str] | None = None,
    filter: dict | None = None,
) -> xr.DataTree:
    from geode.client import get as _get

    return _get(
        data_type,
        start_time,
        end_time,
        vars=vars,
        filter=filter,
    )
