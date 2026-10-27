from typing import Any


_filter_types: dict[str, type] = {}


def register_filter(name: str):
    def decorator(cls):
        _filter_types[name] = cls
        return cls
    return decorator


def make_filter(name: str, kwargs: dict[str, Any]):
    filter_cls = _filter_types.get(name)
    if filter_cls is None:
        raise ValueError(f"Unknown filter: {name}")
    return filter_cls(kwargs)
