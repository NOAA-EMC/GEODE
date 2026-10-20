from typing import Any
import xarray as xr
import numpy as np


filter_types: dict[str, type] = {}

LocationKey = "Location"

def register_filter(name: str):
    def decorator(cls):
        filter_types[name] = cls
        return cls
    return decorator


def apply(datatree, variables: list[str] = [], filters: dict[str, dict[str, Any]] = {}):
    if variables:
        datatree = datatree.map_over_datasets(lambda ds: ds[variables])

    if not filters:
        return datatree

    mask = np.ones_like(datatree[LocationKey].values, dtype=bool)

    for filter_name, kwargs in filters.items():
        filter_cls = filter_types.get(filter_name)
        if filter_cls is None:
            raise ValueError(f"Unknown filter: {filter_name}")
        mask &= filter_cls.make_mask(datatree, kwargs)

    return datatree.map_over_datasets(lambda ds: ds.isel({LocationKey: mask}))
