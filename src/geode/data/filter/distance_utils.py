"""Distance calculation and spatial clustering utilities for GEODE filters.

Pure NumPy implementation to avoid external dependencies like SciPy.
"""

from typing import Any
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
    x = radius_km * np.cos(rad_lat) * np.cos(rad_lon)
    y = radius_km * np.cos(rad_lat) * np.sin(rad_lon)
    z = radius_km * np.sin(rad_lat)
    return np.column_stack([x, y, z])


def cluster_by_distance(
    lats: np.ndarray,
    lons: np.ndarray,
    distance_km: float,
) -> list[list[int]]:
    """Group spatial locations into clusters within distance_km.

    Uses scipy.spatial.cKDTree if installed; otherwise falls back to a fast
    O(N) 3D spatial voxel hash in pure NumPy.
    """
    n_pts = len(lats)
    if n_pts == 0:
        return []
    if n_pts == 1:
        return [[0]]

    # Try fast cKDTree if scipy happens to be available
    try:
        from scipy.spatial import cKDTree

        points = latlon_to_cartesian(lats, lons)
        tree = cKDTree(points)
        chord_dist = float(2.0 * EARTH_RADIUS_KM * np.sin(distance_km / (2.0 * EARTH_RADIUS_KM)))

        visited = np.zeros(n_pts, dtype=bool)
        clusters: list[list[int]] = []

        for i in range(n_pts):
            if visited[i]:
                continue
            neighbors = tree.query_ball_point(points[i], r=chord_dist)
            unassigned = [int(idx) for idx in neighbors if not visited[idx]]
            if unassigned:
                visited[unassigned] = True
                clusters.append(unassigned)

        return clusters

    except ImportError:
        # Pure NumPy O(N) spatial voxel hashing
        points = latlon_to_cartesian(lats, lons)
        voxel_coords = np.floor(points / distance_km).astype(np.int64)

        # Group points sharing the same 3D voxel box
        _, inverse_indices = np.unique(voxel_coords, axis=0, return_inverse=True)
        num_clusters = int(inverse_indices.max() + 1)
        clusters = [[] for _ in range(num_clusters)]
        for idx, cluster_id in enumerate(inverse_indices):
            clusters[cluster_id].append(idx)

        return [c for c in clusters if c]
