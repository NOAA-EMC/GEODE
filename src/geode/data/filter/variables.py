from collections import defaultdict
from collections.abc import Sequence

import xarray as xr

from geode.data.filter.base import AndFilter
from geode.data.filter.factory import register_filter
from geode.data.keys import (
    ChannelKey,
    LatitudeKey,
    LocationKey,
    LongitudeKey,
    TimeKey,
)


@register_filter("variables")
class VariableFilter(AndFilter):
    def __init__(self, arg: Sequence[str]):

        # Add mandatory keys to the argument sequence
        arg = set(arg)
        arg.add(TimeKey)
        arg.add(LocationKey)
        arg.add(LatitudeKey)
        arg.add(LongitudeKey)
        arg.add(ChannelKey)
        arg = list(arg)

        super().__init__(arg)

    def apply(self, dt: xr.DataTree) -> xr.DataTree:
        # Organize variables by group
        groups = defaultdict(list)

        for path in self.arg:
            group, _, variable = path.strip("/").rpartition("/")
            group = f"/{group}" if group else "/"
            groups[group].append(variable)

        # Preserve root attributes
        datasets = {"/": xr.Dataset(attrs=dt.attrs)}

        # Select only requested variables in each group
        for group, variables in groups.items():
            ds = dt[group].to_dataset(inherit="all_coords")
            datasets[group] = ds[list(dict.fromkeys(variables))]

        # Reconstruct the DataTree
        return xr.DataTree.from_dict(datasets, name=dt.name)

    @classmethod
    def _validate(cls, arg: Sequence[str]) -> None:
        if not isinstance(arg, Sequence):
            cls._validation_error("Argument must be a sequence of variable names.")

        if not all(isinstance(i, str) for i in arg):
            cls._validation_error(
                "All elements in the variable sequence must be strings."
            )

        if len(set(arg)) != len(arg):
            cls._validation_error("Variable sequence must not contain duplicate names.")

        if len(arg) == 0:
            cls._validation_error("Variable sequence must not be empty.")
