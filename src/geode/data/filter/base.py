from typing import Any

import xarray as xr


class ValidationError(Exception):
    def __init__(self, filter_type: str, msg: str):
        self.filter_type = filter_type
        super().__init__(f"{filter_type}: {msg}")


class FilterBase:
    def __init__(self, arg: Any):
        self._validate(arg)
        self.arg = arg

    @classmethod
    def _validate(cls, arg: Any) -> None:
        raise NotImplementedError()

    @classmethod
    def _validation_error(cls, msg: str) -> None:
        raise ValidationError(filter_type=cls.__name__, msg=msg)

    @classmethod
    def _warning(cls, msg: str) -> None:
        import warnings
        
        warnings.warn(f"{cls.__name__}: {msg}")


class AndFilter(FilterBase):
    def apply(self, ds: xr.DataTree) -> xr.DataTree:
        raise NotImplementedError()


class OrFilter(FilterBase):
    def make_mask(self, ds: xr.DataTree) -> xr.DataArray:
        raise NotImplementedError()
