from typing import Any
import xarray as xr

from geode.data.filter.base import Filter

filter_types: dict[str, object] = {}

def register_filter(name: str):
    def decorator(cls):
        filter_types[name] = cls()
        return cls
    return decorator

def apply(data: xr.DataTree, vars: list[str], filters: dict[str, Any]) -> xr.DataTree:
    if not filters:
        return data

    # Make the filters
    filter_list: list[Filter] = []
    for filter_name, filter_args in filters.items():
        if filter_name not in filter_types:
            raise ValueError(f"Filter '{filter_name}' not recognized.")

        filter_cls = filter_types[filter_name]
        filter_cls.validate(filter_args)
        filter_list.append(filter_cls.make(filter_args))

    # Split filter kinds
    sel = {}
    where = {}
    for filter in filter_list:
        if filter.kind == Filter.Kind.Select:
            sel.update(filter.kwargs)
        elif filter.kind == Filter.Kind.Where:
            where.update(filter.args)

    if sel:
        data = data.sel(sel)
    if where:
        data = data.where(where)

    return data
