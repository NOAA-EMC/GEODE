from dataclasses import dataclass
from typing import Any
from enum import Enum

import xarray as xr


class ValidationError(Exception):
    def __init__(self, filter_type: str, msg: str):
        self.filter_type = filter_type
        super().__init__(f"{filter_type}: {msg}")


@dataclass
class Filter:
    class Kind(Enum):
        Select = "sel"
        Where = "where"

    kind: Kind
    kwargs: dict[str, Any]


class FilterType:
    @classmethod
    def validate(cls, kwargs: dict[str, Any]) -> None:
        raise NotImplementedError("Filter subclasses must implement the validate method.")

    @classmethod
    def make(cls, kwargs: dict[str, Any]) -> Filter:
        raise NotImplementedError("Filter subclasses must implement the make method.")

    @classmethod
    def _validation_error(cls, msg: str) -> None:
        raise ValidationError(filter_type=cls.__name__, msg=msg)
