"""
3D Room Generation: Floors, Ceilings, and Multi-Room Spatial Relationships.
"""

from __future__ import annotations

import numpy as np
import trimesh
from shapely.geometry import Polygon
from typing import Dict, Any, List, Optional, Tuple

from geometry.schema import Room, Wall
from geometry.geometry.materials import ArchitecturalMaterials


class RoomMeshBuilder:
    """Builds 3D floors and ceilings from room polygons and analyzes multi-room spatial relationships."""

    def __init__(self, default_wall_height: float = 2.8, slab_thickness: float = 0.05):
        self.default_wall_height = default_wall_height
        self.slab_thickness = slab_thickness
        self.floor_mat = ArchitecturalMaterials.floor_material()
        self.ceiling_mat = ArchitecturalMaterials.ceiling_material()

    def build_room(
        self,
        room: Room,
        wall_height: Optional[float] = None,
        as_solid_slab: bool = True
    ) -> Dict[str, Any]:
        """
        Generates 3D floor and ceiling meshes for a room polygon.
        """
        h = wall_height if wall_height is not None else self.default_wall_height
        poly = Polygon(room.polygon)
        if not poly.is_valid:
            poly = poly.buffer(0)

        if poly.area < 1e-4:
            raise ValueError(f"Room '{room.id}' has zero or invalid polygon area.")

        # Triangulate 2D polygon
        vertices_2d, faces_2d = trimesh.creation.triangulate_polygon(poly, engine="earcut")
        n_verts = len(vertices_2d)

        if as_solid_slab and self.slab_thickness > 0:
            # 1. Floor Solid Slab: z from -slab_thickness to 0.0
            # Extrude 2D polygon along -Z
            floor_mesh = trimesh.creation.extrude_polygon(
                poly,
                height=self.slab_thickness,
                engine="earcut"
            )
            # Extrude in trimesh goes from z=0 to z=height; translate down so top surface is at z=0.0
            floor_mesh.apply_translation([0.0, 0.0, -self.slab_thickness])
            floor_mesh.visual.material = self.floor_mat

            # 2. Ceiling Solid Slab: z from wall_height to wall_height + slab_thickness
            ceiling_mesh = trimesh.creation.extrude_polygon(
                poly,
                height=self.slab_thickness,
                engine="earcut"
            )
            ceiling_mesh.apply_translation([0.0, 0.0, h])
            ceiling_mesh.visual.material = self.ceiling_mat
        else:
            # Single-sided planar surfaces
            # Floor at z = 0.0, normals facing +Z
            floor_verts = np.column_stack([vertices_2d, np.zeros(n_verts, dtype=np.float64)])
            floor_faces = np.array(faces_2d, copy=True)
            floor_mesh = trimesh.Trimesh(vertices=floor_verts, faces=floor_faces, process=True)
            # Verify normals point +Z
            if np.mean(floor_mesh.face_normals[:, 2]) < 0:
                floor_mesh.faces = np.fliplr(floor_mesh.faces)
            floor_mesh.visual.material = self.floor_mat

            # Ceiling at z = h, normals facing -Z (down into room)
            ceiling_verts = np.column_stack([vertices_2d, np.full(n_verts, h, dtype=np.float64)])
            ceiling_faces = np.array(faces_2d, copy=True)
            ceiling_mesh = trimesh.Trimesh(vertices=ceiling_verts, faces=ceiling_faces, process=True)
            if np.mean(ceiling_mesh.face_normals[:, 2]) > 0:
                ceiling_mesh.faces = np.fliplr(ceiling_mesh.faces)
            ceiling_mesh.visual.material = self.ceiling_mat

        centroid_pt = [float(poly.centroid.x), float(poly.centroid.y), h / 2.0]
        bounds = [float(b) for b in poly.bounds]

        return {
            "room_id": room.id,
            "room_name": room.name or room.id,
            "floor_mesh": floor_mesh,
            "ceiling_mesh": ceiling_mesh,
            "area": float(poly.area),
            "perimeter": float(poly.length),
            "centroid": centroid_pt,
            "bounds_2d": bounds,
            "wall_height": h
        }

    @staticmethod
    def detect_shared_walls(
        walls: List[Wall],
        rooms: List[Room],
        tolerance: float = 0.05
    ) -> Dict[str, List[str]]:
        """
        Determines which rooms each wall borders.
        Returns a mapping: wall_id -> list of bordering room_ids.
        A wall bordering >= 2 rooms is a shared/partition wall.
        """
        from shapely.geometry import LineString

        wall_to_rooms: Dict[str, List[str]] = {w.id: [] for w in walls}
        room_polys = {r.id: Polygon(r.polygon) for r in rooms}

        for w in walls:
            w_line = LineString([w.start, w.end])
            for r_id, r_poly in room_polys.items():
                # Check distance from wall line to room polygon boundary
                dist = w_line.distance(r_poly.boundary)
                if dist <= tolerance:
                    wall_to_rooms[w.id].append(r_id)

        return wall_to_rooms
