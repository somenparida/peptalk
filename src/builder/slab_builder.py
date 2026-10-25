"""Procedural 3D floor slabs, ceiling slabs, and plinth foundation reconstruction."""

from __future__ import annotations

from typing import List, Optional, Tuple

import numpy as np
import trimesh
from shapely.geometry import Polygon

from src.builder.mesh_utils import triangulate_2d_polygon
from src.config import CONFIG
from src.models import Point2D, RoomPolygon


def extrude_polygon_to_slab(
    points: List[Point2D],
    z_bottom: float,
    z_top: float,
    color: Optional[Tuple[int, int, int, int]] = None,
) -> trimesh.Trimesh:
    """
    Extrudes arbitrary 2D polygon into a watertight 3D prism.
    z_bottom: lower elevation
    z_top: upper elevation
    """
    coords_2d = [p.as_tuple() for p in points]
    if len(coords_2d) > 1 and coords_2d[0] == coords_2d[-1]:
        coords_2d.pop()

    n = len(coords_2d)
    if n < 3:
        return trimesh.Trimesh()

    # Ensure CCW orientation
    poly = Polygon(coords_2d)
    if not poly.exterior.is_ccw:
        coords_2d.reverse()

    # Triangulate top/bottom face
    tri_faces = triangulate_2d_polygon(coords_2d)
    if len(tri_faces) == 0:
        return trimesh.Trimesh()

    # Create 3D vertices: bottom ring (0..n-1), top ring (n..2n-1)
    vertices = np.zeros((2 * n, 3), dtype=np.float64)
    for i, (x, y) in enumerate(coords_2d):
        vertices[i] = [x, y, z_bottom]
        vertices[i + n] = [x, y, z_top]

    faces: List[List[int]] = []

    # Top faces (normal points +z)
    for tri in tri_faces:
        faces.append([int(tri[0]) + n, int(tri[1]) + n, int(tri[2]) + n])

    # Bottom faces (reversed order so normal points -z)
    for tri in tri_faces:
        faces.append([int(tri[0]), int(tri[2]), int(tri[1])])

    # Side quad faces (split into 2 triangles each)
    for i in range(n):
        j = (i + 1) % n
        # Triangle 1: i, j, j + n
        faces.append([i, j, j + n])
        # Triangle 2: i, j + n, i + n
        faces.append([i, j + n, i + n])

    faces_arr = np.array(faces, dtype=np.int64)
    mesh = trimesh.Trimesh(vertices=vertices, faces=faces_arr, process=False)

    if color is not None:
        mesh.visual.vertex_colors = np.tile(color, (len(vertices), 1))

    return mesh


class SlabMeshBuilder:
    """
    Constructs 3D floor slabs, ceiling slabs, and site plinths.
    """

    def build_room_floors(self, rooms: List[RoomPolygon]) -> trimesh.Trimesh:
        """Extrudes floor slabs for each individual room."""
        floor_meshes: List[trimesh.Trimesh] = []
        z_top = 0.0
        z_bottom = -CONFIG.FLOOR_SLAB_THICKNESS

        for room in rooms:
            if len(room.points) >= 3:
                mesh = extrude_polygon_to_slab(
                    room.points,
                    z_bottom=z_bottom,
                    z_top=z_top,
                    color=room.color or CONFIG.COLOR_FLOOR,
                )
                if not mesh.is_empty:
                    floor_meshes.append(mesh)

        return trimesh.util.concatenate(floor_meshes) if floor_meshes else trimesh.Trimesh()

    def build_ceilings(
        self, rooms: List[RoomPolygon], wall_height: float = CONFIG.WALL_HEIGHT
    ) -> trimesh.Trimesh:
        """
        Extrudes ceiling slabs for each room.
        Positioned at z = wall_height to z = wall_height + CEILING_SLAB_THICKNESS.
        """
        ceiling_meshes: List[trimesh.Trimesh] = []
        z_bottom = wall_height
        z_top = wall_height + CONFIG.CEILING_SLAB_THICKNESS

        for room in rooms:
            if len(room.points) >= 3:
                mesh = extrude_polygon_to_slab(
                    room.points,
                    z_bottom=z_bottom,
                    z_top=z_top,
                    color=CONFIG.COLOR_CEILING,
                )
                if not mesh.is_empty:
                    ceiling_meshes.append(mesh)

        return trimesh.util.concatenate(ceiling_meshes) if ceiling_meshes else trimesh.Trimesh()

    def build_site_plinth(
        self, rooms: List[RoomPolygon], offset: float = 0.20
    ) -> trimesh.Trimesh:
        """Creates unified foundation plinth slab below all rooms."""
        all_pts: List[Point2D] = []
        for r in rooms:
            all_pts.extend(r.points)

        if not all_pts:
            return trimesh.Trimesh()

        xs = [p.x for p in all_pts]
        ys = [p.y for p in all_pts]
        min_x, max_x = min(xs) - offset, max(xs) + offset
        min_y, max_y = min(ys) - offset, max(ys) + offset

        bbox_pts = [
            Point2D(min_x, min_y),
            Point2D(max_x, min_y),
            Point2D(max_x, max_y),
            Point2D(min_x, max_y),
        ]

        return extrude_polygon_to_slab(
            bbox_pts,
            z_bottom=-(CONFIG.FLOOR_SLAB_THICKNESS + 0.10),
            z_top=-CONFIG.FLOOR_SLAB_THICKNESS,
            color=(180, 175, 170, 255),
        )
