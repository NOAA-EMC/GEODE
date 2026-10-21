from dataclasses import dataclass
from typing import Any
from enum import Enum

import xarray as xr


class ValidationError(Exception):
    def __init__(self, filter_type: str, msg: str):
        self.filter_type = filter_type
        super().__init__(f"{filter_type}: {msg}")


class FilterType(Enum):
    INTERSECT = "intersect",
    UNION = "union"


class FilterBase:
    def __init__(self, kwargs: dict[str, Any], type: FilterType = FilterType.UNION):
        self._validate(kwargs)
        self.kwargs = kwargs
        self.type = type

    def make_mask(self, ds: xr.DataTree):
        raise NotImplementedError()

    @classmethod
    def _validate(cls, kwargs: dict[str, Any]) -> None:
        raise NotImplementedError()

    @classmethod
    def _validation_error(cls, msg: str) -> None:
        raise ValidationError(filter_type=cls.__name__, msg=msg)
