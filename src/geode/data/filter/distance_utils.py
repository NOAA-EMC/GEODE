"""Distance calculation and spatial clustering utilities for GEODE filters.

Deterministic, vectorized pure-NumPy 3D spatial voxel hashing.
"""

import numpy as np

EARTH_RADIUS_KM = 6371.0088


def latlon_to_cartesian(
    lats: np.ndarray,
    lons: np.ndarray,
    radius_km: float = EARTH_RADIUS_KM,
) -> np.ndarray:
    """Convert lat/lon degrees to 3D Cartesian coordinates (km)."""
    rad_lat = np.radians(lats)
    rad_lon = np.radians(lons)
    cos_lat = np.cos(rad_lat)
    x = radius_km * cos_lat * np.cos(rad_lon)
    y = radius_km * cos_lat * np.sin(rad_lon)
    z = radius_km * np.sin(rad_lat)
    return np.column_stack([x, y, z])


def cluster_by_distance_flat(
    lats: np.ndarray,
    lons: np.ndarray,
    distance_km: float,
) -> tuple[np.ndarray, np.ndarray]:
    """Group spatial locations into clusters within distance_km.

    Uses deterministic 3D Cartesian voxel hashing (cubic cells with diagonal
    ``distance_km``, i.e. side length ``distance_km / sqrt(3)``) so every
    pair within a cluster has chord distance <= ``distance_km`` with identical
    results across all environments and zero Python loops.

    Returns contiguous CSR-style index arrays ``(flat_indices, group_starts)``.
    """
    n_pts = len(lats)
    if n_pts == 0:
        return np.empty(0, dtype=np.int64), np.empty(0, dtype=np.int64)
    if n_pts == 1:
        return np.array([0], dtype=np.int64), np.array([0], dtype=np.int64)

    points = latlon_to_cartesian(lats, lons)
    cell_size_km = distance_km / np.sqrt(3.0)
    voxel_coords = np.floor(points / cell_size_km).astype(np.int64)
    vx, vy, vz = voxel_coords[:, 0], voxel_coords[:, 1], voxel_coords[:, 2]

    # Pack (vx, vy, vz) into a single int64 key when coordinates fit in 21 signed bits
    # (valid for any distance_km >= ~0.011 km on Earth)
    bit_limit = 1 << 20
    if (
        np.abs(vx).max() < bit_limit
        and np.abs(vy).max() < bit_limit
        and np.abs(vz).max() < bit_limit
    ):
        offset = bit_limit
        voxel_keys = ((vx + offset) << 42) | ((vy + offset) << 21) | (vz + offset)
        order = np.argsort(voxel_keys, kind="stable")
        sorted_keys = voxel_keys[order]
        starts = np.r_[0, np.flatnonzero(sorted_keys[1:] != sorted_keys[:-1]) + 1]
    else:
        order = np.lexsort((vz, vy, vx))
        s_vx, s_vy, s_vz = vx[order], vy[order], vz[order]
        diff = (
            (s_vx[1:] != s_vx[:-1]) | (s_vy[1:] != s_vy[:-1]) | (s_vz[1:] != s_vz[:-1])
        )
        starts = np.r_[0, np.flatnonzero(diff) + 1]

    return order.astype(np.int64, copy=False), starts.astype(np.int64, copy=False)


def cluster_by_distance(
    lats: np.ndarray,
    lons: np.ndarray,
    distance_km: float,
) -> list[list[int]]:
    """Group spatial locations into clusters within distance_km (list-of-lists wrapper)."""
    flat_indices, group_starts = cluster_by_distance_flat(lats, lons, distance_km)
    if len(group_starts) == 0:
        return []
    splits = np.split(flat_indices, group_starts[1:])
    return [c.tolist() for c in splits]
