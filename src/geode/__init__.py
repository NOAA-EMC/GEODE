__all__ = ["get"]


def get(*args, **kwargs):
    from geode.client import get as _get

    return _get(*args, **kwargs)
