"""Low-level procedural 3D mesh generation primitives."""

from __future__ import annotations

import math
from typing import List, Optional, Tuple

import numpy as np
import trimesh

from src.models import Point2D


def create_transformed_box(
    s0: float,
    s1: float,
    t0: float,
    t1: float,
    z0: float,
    z1: float,
    start: Point2D,
    direction: Tuple[float, float],
    normal: Tuple[float, float],
    color: Optional[Tuple[int, int, int, int]] = None,
) -> trimesh.Trimesh:
    """
    Constructs a closed, watertight 3D box oriented along a 2D line segment.
    s: distance along tangent
    t: distance along normal
    z: vertical elevation
    """
    if s1 <= s0 or t1 <= t0 or z1 <= z0:
        return trimesh.Trimesh()

    # 8 Local box vertices: (s, t, z)
    local_verts = [
        (s0, t0, z0),  # 0
        (s1, t0, z0),  # 1
        (s1, t1, z0),  # 2
        (s0, t1, z0),  # 3
        (s0, t0, z1),  # 4
        (s1, t0, z1),  # 5
        (s1, t1, z1),  # 6
        (s0, t1, z1),  # 7
    ]

    ux, uy = direction
    nx, ny = normal

    # Transform to world coordinates: (x, y, z)
    world_verts = np.zeros((8, 3), dtype=np.float64)
    for i, (s, t, z) in enumerate(local_verts):
        world_verts[i, 0] = start.x + s * ux + t * nx
        world_verts[i, 1] = start.y + s * uy + t * ny
        world_verts[i, 2] = z

    # 12 Triangles with outward normals
    faces = np.array([
        # Bottom (z = z0)
        [0, 2, 1],
        [0, 3, 2],
        # Top (z = z1)
        [4, 5, 6],
        [4, 6, 7],
        # Front (t = t0)
        [0, 1, 5],
        [0, 5, 4],
        # Back (t = t1)
        [2, 3, 7],
        [2, 7, 6],
        # Left (s = s0)
        [3, 0, 4],
        [3, 4, 7],
        # Right (s = s1)
        [1, 2, 6],
        [1, 6, 5],
    ], dtype=np.int64)

    mesh = trimesh.Trimesh(vertices=world_verts, faces=faces, process=False)
    if color is not None:
        mesh.visual.vertex_colors = np.tile(color, (len(world_verts), 1))

    return mesh


def triangulate_2d_polygon(coords: List[Tuple[float, float]]) -> np.ndarray:
    """
    Triangulates simple 2D polygon using ear clipping algorithm.
    Returns array of triangular face indices (N, 3).
    """
    # Remove duplicate last coordinate if closed
    pts = list(coords)
    if len(pts) > 1 and pts[0] == pts[-1]:
        pts.pop()

    n = len(pts)
    if n < 3:
        return np.empty((0, 3), dtype=np.int64)
    if n == 3:
        return np.array([[0, 1, 2]], dtype=np.int64)

    # Use Shapely triangulation / ear-clipping
    from shapely.geometry import Polygon
    from shapely.ops import triangulate

    poly = Polygon(pts)
    if not poly.is_valid:
        from shapely.validation import make_valid
        poly = make_valid(poly)
        if hasattr(poly, "geoms"):
            poly = max(poly.geoms, key=lambda g: g.area)

    triangles = triangulate(poly)
    tri_coords = []
    for tri in triangles:
        if poly.contains(tri.centroid):
            c = list(tri.exterior.coords)[:-1]
            tri_coords.append(c)

    if not tri_coords:
        # Fallback fan triangulation
        faces = [[0, i, i + 1] for i in range(1, n - 1)]
        return np.array(faces, dtype=np.int64)

    # Map triangle coords to vertex indices
    faces = []
    # Build unique vertex list
    all_pts = pts.copy()
    for tri in tri_coords:
        face = []
        for tc in tri:
            # find closest existing index
            dists = [math.hypot(tc[0] - p[0], tc[1] - p[1]) for p in all_pts]
            min_idx = int(np.argmin(dists))
            if dists[min_idx] < 1e-4:
                face.append(min_idx)
            else:
                face.append(len(all_pts))
                all_pts.append(tc)
        faces.append(face)

    return np.array(faces, dtype=np.int64)
