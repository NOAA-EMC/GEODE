"""Distance calculation and spatial clustering utilities for GEODE filters.

Pure NumPy implementation with optional SciPy cKDTree acceleration.
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

    Returns contiguous CSR-style index arrays ``(flat_indices, group_starts)``
    to avoid ragged list allocations and per-cluster Python loops.
    """
    n_pts = len(lats)
    if n_pts == 0:
        return np.empty(0, dtype=np.int64), np.empty(0, dtype=np.int64)
    if n_pts == 1:
        return np.array([0], dtype=np.int64), np.array([0], dtype=np.int64)

    points = latlon_to_cartesian(lats, lons)

    # 1. Fast parallel cKDTree ball query if SciPy is available
    try:
        from scipy.spatial import cKDTree

        tree = cKDTree(points)
        chord_dist = float(
            2.0 * EARTH_RADIUS_KM * np.sin(min(distance_km / (2.0 * EARTH_RADIUS_KM), 1.0))
        )

        visited = np.zeros(n_pts, dtype=bool)
        flat_indices = np.empty(n_pts, dtype=np.int64)
        group_starts: list[int] = []
        cursor = 0

        # Query in batches to minimize Python-to-C call overhead and enable multi-threading
        batch_size = 8192
        for batch_start in range(0, n_pts, batch_size):
            batch_end = min(batch_start + batch_size, n_pts)
            unvisited_offsets = np.flatnonzero(~visited[batch_start:batch_end])
            if len(unvisited_offsets) == 0:
                continue

            query_indices = batch_start + unvisited_offsets
            neighbor_lists = tree.query_ball_point(
                points[query_indices], r=chord_dist, workers=-1
            )

            for idx, neighbors in zip(query_indices, neighbor_lists):
                if visited[idx]:
                    continue
                nbr_arr = np.asarray(neighbors, dtype=np.int64)
                unassigned = nbr_arr[~visited[nbr_arr]]
                if len(unassigned) > 0:
                    visited[unassigned] = True
                    group_starts.append(cursor)
                    next_cursor = cursor + len(unassigned)
                    flat_indices[cursor:next_cursor] = unassigned
                    cursor = next_cursor

        return flat_indices[:cursor], np.asarray(group_starts, dtype=np.int64)

    # 2. Pure NumPy 3D voxel hash using 64-bit integer key packing
    except ImportError:
        voxel_coords = np.floor(points / distance_km).astype(np.int64)
        vx, vy, vz = voxel_coords[:, 0], voxel_coords[:, 1], voxel_coords[:, 2]

        # Pack (vx, vy, vz) into a single int64 key when coordinates fit in 21 signed bits
        # (valid for any distance_km >= ~0.007 km on Earth)
        bit_limit = 1 << 20
        if (
            np.abs(vx).max() < bit_limit
            and np.abs(vy).max() < bit_limit
            and np.abs(vz).max() < bit_limit
        ):
            offset = bit_limit
            voxel_keys = ((vx + offset) << 42) | ((vy + offset) << 21) | (vz + offset)
            order = np.argsort(voxel_keys)
            sorted_keys = voxel_keys[order]
            starts = np.r_[0, np.flatnonzero(sorted_keys[1:] != sorted_keys[:-1]) + 1]
        else:
            order = np.lexsort((vz, vy, vx))
            s_vx, s_vy, s_vz = vx[order], vy[order], vz[order]
            diff = (s_vx[1:] != s_vx[:-1]) | (s_vy[1:] != s_vy[:-1]) | (s_vz[1:] != s_vz[:-1])
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
