from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from geode.client import get as get


def __getattr__(name: str) -> Any:
    if name == "get":
        from geode.client import get

        return get
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")

__all__ = ["get"]
