from dataclasses import dataclass
from typing import Any
from enum import Enum

import xarray as xr


class ValidationError(Exception):
    def __init__(self, filter_type: str, msg: str):
        self.filter_type = filter_type
        super().__init__(f"{filter_type}: {msg}")


class FilterBase:
    def __init__(self):
       pass

    @classmethod
    def make_mask(cls, ds: xr.DataTree, kwargs: dict[str, Any]):
        cls._validate(kwargs)
        return cls._make_mask(ds, kwargs)

    @classmethod
    def _validate(cls, args: Any) -> None:
        raise NotImplementedError()

    @classmethod
    def _make_mask(cls, ds: xr.DataTree, kwargs: dict[str, Any]):
        raise NotImplementedError()

    @classmethod
    def _validation_error(cls, msg: str) -> None:
        raise ValidationError(filter_type=cls.__name__, msg=msg)
