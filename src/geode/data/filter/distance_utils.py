"""Spatial distance, clustering, and resolution validation utilities."""

import math
import numbers
from collections.abc import Callable, Mapping
from typing import Any, NoReturn

import numpy as np

try:
    from scipy.spatial import cKDTree as _cKDTree
except ImportError:
    _cKDTree = None

EARTH_RADIUS_KM = 6371.0
_INV_SQRT3 = 1.0 / math.sqrt(3.0)


def _is_positive_finite_number(value: Any) -> bool:
    if isinstance(value, (bool, np.bool_)) or not isinstance(value, numbers.Real):
        return False
    val = float(value)
    return math.isfinite(val) and val > 0.0


def validate_spatial_resolution(
    arg: Any,
    error_fn: Callable[[str], NoReturn],
) -> None:
    """Validate mutually exclusive, finite, strictly positive 'grid' or 'distance'."""
    if not isinstance(arg, Mapping):
        error_fn("Arguments must be a mapping.")

    has_grid = "grid" in arg
    has_distance = "distance" in arg

    if not has_grid and not has_distance:
        error_fn("Requires either 'grid' or 'distance' key.")
    if has_grid and has_distance:
        error_fn("Specify either 'grid' or 'distance', not both.")

    if has_grid:
        grid = arg["grid"]
        if isinstance(grid, (list, tuple)):
            valid_grid = len(grid) == 2 and all(
                _is_positive_finite_number(v) for v in grid
            )
        elif isinstance(grid, np.ndarray):
            valid_grid = (
                grid.ndim == 1
                and grid.shape == (2,)
                and all(_is_positive_finite_number(v) for v in grid)
            )
        else:
            valid_grid = _is_positive_finite_number(grid)

        if not valid_grid:
            error_fn(
                f"Invalid 'grid': {grid!r}. Expected a finite positive number "
                "or a 2-element sequence of finite positive numbers."
            )

    if has_distance and not _is_positive_finite_number(arg["distance"]):
        error_fn(
            f"Invalid 'distance': {arg['distance']!r}. Expected a finite positive number."
        )


def latlon_to_cartesian(lats: np.ndarray, lons: np.ndarray) -> np.ndarray:
    """Convert latitude/longitude in degrees to 3D unit-sphere Cartesian coordinates."""
    lat_rad = np.radians(lats)
    lon_rad = np.radians(lons)
    cos_lat = np.cos(lat_rad)
    return np.column_stack(
        (
            cos_lat * np.cos(lon_rad),
            cos_lat * np.sin(lon_rad),
            np.sin(lat_rad),
        )
    )


def cluster_by_distance_flat(
    lats: np.ndarray,
    lons: np.ndarray,
    distance_km: float,
) -> tuple[np.ndarray, np.ndarray]:
    """Group points within ``distance_km`` using 3D Cartesian voxel leader clustering.

    Returns ``(flat_indices, group_starts)`` where ``flat_indices`` concatenates
    member indices for each cluster and ``group_starts`` gives the start offset
    of each cluster in ``flat_indices``.
    """
    if not math.isfinite(distance_km) or distance_km <= 0.0:
        raise ValueError(
            f"distance_km must be a finite positive number, got {distance_km!r}"
        )

    n_obs = len(lats)
    if n_obs == 0:
        return np.empty(0, dtype=np.int64), np.empty(0, dtype=np.int64)
    if distance_km >= np.pi * EARTH_RADIUS_KM:
        return np.arange(n_obs, dtype=np.int64), np.zeros(1, dtype=np.int64)

    xyz = latlon_to_cartesian(lats, lons)
    half_angle = min(float(distance_km) / (2.0 * EARTH_RADIUS_KM), np.pi / 2.0)
    chord = 2.0 * np.sin(half_angle)
    chord_sq = chord * chord

    # Sub-voxel width chord / sqrt(3) guarantees every point in a sub-voxel lies
    # within `chord` of that sub-voxel's first observation.
    sub_chord = chord * _INV_SQRT3
    sub_voxels = np.floor(xyz / sub_chord).astype(np.int64)
    v_min = int(sub_voxels.min())
    v_max = int(sub_voxels.max())

    if (v_min >= -(1 << 20)) and (v_max < (1 << 20)):
        bias = 1 << 20
        voxel_keys = (
            ((sub_voxels[:, 0] + bias) << 42)
            | ((sub_voxels[:, 1] + bias) << 21)
            | (sub_voxels[:, 2] + bias)
        )
        order = np.argsort(voxel_keys, kind="stable")
        sorted_keys = voxel_keys[order]
        first_in_voxel = np.r_[True, sorted_keys[1:] != sorted_keys[:-1]]
    else:
        order = np.lexsort((sub_voxels[:, 2], sub_voxels[:, 1], sub_voxels[:, 0]))
        sv = sub_voxels[order]
        first_in_voxel = np.r_[
            True,
            (sv[1:, 0] != sv[:-1, 0])
            | (sv[1:, 1] != sv[:-1, 1])
            | (sv[1:, 2] != sv[:-1, 2]),
        ]

    seed_indices = np.sort(order[first_in_voxel])
    seed_xyz = xyz[seed_indices]
    coarse_voxels = np.floor(seed_xyz / chord).astype(np.int64)

    neighbor_offsets = tuple(
        (dx, dy, dz) for dx in (-1, 0, 1) for dy in (-1, 0, 1) for dz in (-1, 0, 1)
    )
    voxel_leaders: dict[tuple[int, int, int], list[tuple[float, float, float]]] = {}
    leader_indices: list[int] = []

    for s_idx, px, py, pz, vx, vy, vz in zip(
        seed_indices.tolist(),
        seed_xyz[:, 0].tolist(),
        seed_xyz[:, 1].tolist(),
        seed_xyz[:, 2].tolist(),
        coarse_voxels[:, 0].tolist(),
        coarse_voxels[:, 1].tolist(),
        coarse_voxels[:, 2].tolist(),
    ):
        candidates = voxel_leaders.get((vx, vy, vz))
        if candidates is not None:
            covered = False
            for lx, ly, lz in candidates:
                dx = px - lx
                dy = py - ly
                dz = pz - lz
                if dx * dx + dy * dy + dz * dz <= chord_sq:
                    covered = True
                    break
            if covered:
                continue

        leader_indices.append(s_idx)
        entry = (px, py, pz)
        for dx, dy, dz in neighbor_offsets:
            n_key = (vx + dx, vy + dy, vz + dz)
            bucket = voxel_leaders.get(n_key)
            if bucket is None:
                voxel_leaders[n_key] = [entry]
            else:
                bucket.append(entry)

    n_clusters = len(leader_indices)
    if n_clusters == 1:
        return np.arange(n_obs, dtype=np.int64), np.zeros(1, dtype=np.int64)

    leaders_xyz = xyz[leader_indices]

    if n_clusters <= 2048:
        chunk_size = max(1, 2_000_000 // n_clusters)
        cluster_ids = np.empty(n_obs, dtype=np.int64)
        leaders_T = np.ascontiguousarray(leaders_xyz.T)
        for start in range(0, n_obs, chunk_size):
            end = min(start + chunk_size, n_obs)
            dots = xyz[start:end] @ leaders_T
            cluster_ids[start:end] = np.argmax(dots, axis=1)
    elif _cKDTree is not None:
        tree = _cKDTree(leaders_xyz)
        _, cluster_ids = tree.query(xyz, k=1, workers=-1)
        cluster_ids = np.asarray(cluster_ids, dtype=np.int64)
    else:
        obs_coarse = np.floor(xyz / chord).astype(np.int64)
        voxel_leaders_id: dict[
            tuple[int, int, int], list[tuple[int, float, float, float]]
        ] = {}
        for cid, (lx, ly, lz, vx, vy, vz) in enumerate(
            zip(
                leaders_xyz[:, 0].tolist(),
                leaders_xyz[:, 1].tolist(),
                leaders_xyz[:, 2].tolist(),
                obs_coarse[leader_indices, 0].tolist(),
                obs_coarse[leader_indices, 1].tolist(),
                obs_coarse[leader_indices, 2].tolist(),
            )
        ):
            for dx, dy, dz in neighbor_offsets:
                voxel_leaders_id.setdefault((vx + dx, vy + dy, vz + dz), []).append(
                    (cid, lx, ly, lz)
                )
        cids_list = [0] * n_obs
        for idx, (px, py, pz, vx, vy, vz) in enumerate(
            zip(
                xyz[:, 0].tolist(),
                xyz[:, 1].tolist(),
                xyz[:, 2].tolist(),
                obs_coarse[:, 0].tolist(),
                obs_coarse[:, 1].tolist(),
                obs_coarse[:, 2].tolist(),
            )
        ):
            best_cid = 0
            best_d = 1e9
            for cid, lx, ly, lz in voxel_leaders_id[(vx, vy, vz)]:
                d = (px - lx) ** 2 + (py - ly) ** 2 + (pz - lz) ** 2
                if d < best_d:
                    best_d = d
                    best_cid = cid
            cids_list[idx] = best_cid
        cluster_ids = np.array(cids_list, dtype=np.int64)

    flat_indices = np.argsort(cluster_ids, kind="stable").astype(np.int64, copy=False)
    sorted_ids = cluster_ids[flat_indices]
    group_starts = np.r_[0, np.where(sorted_ids[1:] != sorted_ids[:-1])[0] + 1].astype(
        np.int64, copy=False
    )
    return flat_indices, group_starts
