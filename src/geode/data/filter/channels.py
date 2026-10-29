from collections.abc import Sequence

import numpy as np
import xarray as xr

from geode.data.filter.base import AndFilter
from geode.data.filter.factory import register_filter
from geode.data.keys import ChannelKey


@register_filter("channels")
class ChannelFilter(AndFilter):
    def __init__(self, arg: Sequence[int]):
        super().__init__(arg)

    def apply(self, dt: xr.DataTree) -> xr.DataTree:
        channels = dt[ChannelKey].values[:]
        mask = np.zeros_like(dt[ChannelKey].values, dtype=bool)
        for i in self.arg:
            mask[np.where(channels == i)] = True

        return dt.map_over_datasets(
            lambda ds: ds.isel({ChannelKey: mask}, missing_dims="ignore")
        )

    @classmethod
    def _validate(cls, arg: Sequence[int]) -> None:
        if not isinstance(arg, Sequence):
            cls._validation_error("Argument must be a sequence of channel indices.")

        if not all(isinstance(i, int) for i in arg):
            cls._validation_error(
                "All elements in the channel sequence must be integers."
            )

        # make sure the channel indices are in the correct range
        if not all(i > 0 for i in arg):
            cls._validation_error("All channel indices must be positive.")

        if len(set(arg)) != len(arg):
            cls._validation_error(
                "Channel sequence must not contain duplicate indices."
            )

        if len(arg) == 0:
            cls._validation_error("Channel sequence must not be empty.")
