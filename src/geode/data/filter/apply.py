from typing import Any

import numpy as np
import xarray as xr

from geode.data.filter.base import AndFilter, OrFilter
from geode.data.filter.factory import make_filter
from geode.data.keys import LocationKey


def apply(
    datatree: xr.DataTree,
    start_time: np.datetime64,
    end_time: np.datetime64,
    filters: list[dict[str, Any]] | None = None,
):
    filters = filters or []

    # Strategicaly order the filters
    ordered_filters = []
    ordered_filters.extend([f for f in filters if "variables" in f])
    ordered_filters.extend([f for f in filters if "channels" in f])
    ordered_filters.append(
        {"time_window": {"start_time": start_time, "end_time": end_time}}
    )
    ordered_filters.extend(
        [f for f in filters if "variables" not in f and "channels" not in f]
    )

    # Apply the filters to the datatree
    and_filters = []
    or_filters = []
    for filter_dict in ordered_filters:
        filter_name, kwargs = next(iter(filter_dict.items()))
        filter = make_filter(filter_name, kwargs)
        if isinstance(filter, AndFilter):
            and_filters.append(filter)
        elif isinstance(filter, OrFilter):
            or_filters.append(filter)

    # Temporal filters are ANDed. We update the datatree with each filter's mask
    # to save computation by applying each filter sequentially
    for filter in and_filters:
        datatree = filter.apply(datatree)

    # Spatial filters are applied with an OR operation
    if or_filters:
        mask = np.zeros_like(datatree[LocationKey].values, dtype=bool)
        for filter in or_filters:
            mask |= filter.make_mask(datatree)
        datatree = datatree.map_over_datasets(lambda ds: ds.isel({LocationKey: mask}))

    return datatree
