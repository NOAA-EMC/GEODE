"""Deterministic rectangularization of replicated BUFR data."""

import numpy as np
import xarray as xr


def rectangularize_field(
    rows: list, length: int | None = None, fill_value=np.nan
) -> tuple[np.ndarray, np.ndarray]:
    """Pad ragged per-location sequences into a rectangular array.

    Parameters
    ----------
    rows : list
        One sequence per location (may have different lengths).
    length : int, optional
        Exact output length of the replication axis. Defaults to the longest
        row. Rows longer than ``length`` raise ``ValueError``.
    fill_value : scalar
        Value used for padding.

    Returns
    -------
    tuple[numpy.ndarray, numpy.ndarray]
        ``(values, counts)`` with shapes ``(n, length)`` and ``(n,)``.
    """
    counts = np.array([len(row) for row in rows], dtype=np.int64)
    longest = int(counts.max()) if counts.size else 0
    width = longest if length is None else length
    if longest > width:
        raise ValueError(
            f"FATAL ERROR: replication length {longest} exceeds limit {width}"
        )
    values = np.full((len(rows), width), fill_value)
    for i, row in enumerate(rows):
        values[i, : len(row)] = row
    return values, counts


def normalize_dataset(
    dataset: xr.Dataset,
    dimension_sizes: dict[str, int | None] | None = None,
    max_replication_length: int | None = None,
) -> xr.Dataset:
    """Pad replication dimensions to a deterministic size and sort variables.

    Parameters
    ----------
    dataset : xarray.Dataset
        Decoded node dataset.
    dimension_sizes : dict, optional
        Fixed sizes from the schema; used to validate fixed replication.
    max_replication_length : int, optional
        If set, delayed replication dimensions are padded to exactly this size
        so appends are shape-compatible; larger data raises ``ValueError``.

    Returns
    -------
    xarray.Dataset
        Dataset with variables in sorted order and padded dimensions.
    """
    dimension_sizes = dimension_sizes or {}
    for dim, size in dataset.sizes.items():
        if dim == "Location":
            continue
        target = dimension_sizes.get(dim)
        if target is not None:
            if size != target:
                raise ValueError(
                    f"FATAL ERROR: dimension '{dim}' has size {size}, expected {target}"
                )
        elif max_replication_length is not None:
            if size > max_replication_length:
                raise ValueError(
                    f"FATAL ERROR: dimension '{dim}' size {size} exceeds "
                    f"max_replication_length {max_replication_length}"
                )
            if size < max_replication_length:
                dataset = dataset.pad({dim: (0, max_replication_length - size)})
    return dataset[sorted(dataset.data_vars)]
