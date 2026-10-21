from typing import Any
import xarray as xr
import numpy as np

from geode.data.filter.base import FilterType
from geode.data.filter.factory import make_filter


LocationKey = "Location"

def apply(datatree, variables: list[str] = [], filters: list[dict[str, Any]] = []):
    if variables:
        datatree = datatree.map_over_datasets(lambda ds: ds[variables])

    if not filters:
        return datatree

    intersect_filters = []
    union_groups: dict[str, list] = {}
    for filter_dict in filters:
        filter_name, kwargs = next(iter(filter_dict.items()))
        filter = make_filter(filter_name, kwargs)
        if filter.type == FilterType.INTERSECT:
            intersect_filters.append(filter)
        else:
            union_groups.setdefault(filter_name, []).append(filter)
    
    mask = np.ones_like(datatree[LocationKey].values, dtype=bool)
    for filter in intersect_filters:
        mask &= filter.make_mask(datatree)

    for group in union_groups.values():
        group_mask = np.zeros_like(mask)
        for filter in group:
            group_mask |= filter.make_mask(datatree)
        mask &= group_mask

    return datatree.map_over_datasets(lambda ds: ds.isel({LocationKey: mask}))
