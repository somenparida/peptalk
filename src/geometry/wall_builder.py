"""
Volumetric 3D Wall Generation with true geometric openings for doors and windows.
"""

from __future__ import annotations

import math
from typing import List, Tuple, Optional, Dict, Any
import numpy as np
import trimesh

from src.schema import Wall, Door, Window
from src.geometry.materials import ArchitecturalMaterials


def _create_box_mesh(
    p0: np.ndarray,
    u_vec: np.ndarray,
    n_vec: np.ndarray,
    s_range: Tuple[float, float],
    w_range: Tuple[float, float],
    z_range: Tuple[float, float],
) -> trimesh.Trimesh:
    """
    Creates a solid volumetric rectangular box in local coordinate space:
    P(s, w, z) = p0 + s * u_vec + w * n_vec + z * [0, 0, 1]
    """
    s0, s1 = s_range
    w0, w1 = w_range
    z0, z1 = z_range

    if s1 <= s0 or w1 <= w0 or z1 <= z0:
        return trimesh.Trimesh()

    # 8 local corner coordinates
    local_coords = np.array([
        [s0, w0, z0],  # 0
        [s1, w0, z0],  # 1
        [s1, w1, z0],  # 2
        [s0, w1, z0],  # 3
        [s0, w0, z1],  # 4
        [s1, w0, z1],  # 5
        [s1, w1, z1],  # 6
        [s0, w1, z1],  # 7
    ], dtype=np.float64)

    # Transform to world space
    # p = p0 + s * u + w * n + z * z_hat
    z_hat = np.array([0.0, 0.0, 1.0], dtype=np.float64)
    vertices = (
        p0[None, :]
        + local_coords[:, 0:1] * u_vec[None, :]
        + local_coords[:, 1:2] * n_vec[None, :]
        + local_coords[:, 2:3] * z_hat[None, :]
    )

    # 12 triangular faces with outward-facing normals
    faces = np.array([
        # Bottom face (z = z0, normal -Z)
        [0, 2, 1], [0, 3, 2],
        # Top face (z = z1, normal +Z)
        [4, 5, 6], [4, 6, 7],
        # Front face (w = w0, normal -N)
        [0, 1, 5], [0, 5, 4],
        # Back face (w = w1, normal +N)
        [2, 3, 7], [2, 7, 6],
        # Left face (s = s0, normal -U)
        [0, 4, 7], [0, 7, 3],
        # Right face (s = s1, normal +U)
        [1, 2, 6], [1, 6, 5]
    ], dtype=np.int32)

    return trimesh.Trimesh(vertices=vertices, faces=faces, process=True)


class WallMeshBuilder:
    """Builds volumetric 3D walls and opening accessories (frames, leaves, glass)."""

    def __init__(self, default_wall_height: float = 2.8):
        self.default_wall_height = default_wall_height
        self.wall_mat = ArchitecturalMaterials.wall_material()
        self.door_frame_mat = ArchitecturalMaterials.door_frame_material()
        self.door_leaf_mat = ArchitecturalMaterials.door_leaf_material()
        self.win_frame_mat = ArchitecturalMaterials.window_frame_material()
        self.win_glass_mat = ArchitecturalMaterials.window_glass_material()

    def build_wall_with_openings(
        self,
        wall: Wall,
        doors: List[Door],
        windows: List[Window],
        build_accessories: bool = True
    ) -> Dict[str, Any]:
        """
        Generates volumetric 3D wall mesh with true physical openings.
        Returns a dict containing:
        - "wall_mesh": trimesh.Trimesh (solid wall geometry with openings)
        - "door_meshes": list of dicts with frame and leaf meshes
        - "window_meshes": list of dicts with frame and glass meshes
        """
        p0 = np.array([wall.start[0], wall.start[1], 0.0], dtype=np.float64)
        p1 = np.array([wall.end[0], wall.end[1], 0.0], dtype=np.float64)

        d = p1 - p0
        length = float(np.linalg.norm(d[:2]))
        if length < 1e-4:
            raise ValueError(f"Wall '{wall.id}' has zero length.")

        # Tangent and Normal in horizontal plane
        u_vec = np.array([d[0] / length, d[1] / length, 0.0], dtype=np.float64)
        n_vec = np.array([-u_vec[1], u_vec[0], 0.0], dtype=np.float64)

        t = wall.thickness
        w_range = (-t / 2.0, t / 2.0)
        wall_height = wall.height or self.default_wall_height

        # Collect and sort all openings along the wall
        openings: List[Dict[str, Any]] = []

        for d_obj in doors:
            openings.append({
                "type": "door",
                "id": d_obj.id,
                "start": max(0.0, d_obj.offset),
                "end": min(length, d_obj.offset + d_obj.width),
                "height": min(wall_height, d_obj.height),
                "sill_height": 0.0,
                "obj": d_obj
            })

        for w_obj in windows:
            openings.append({
                "type": "window",
                "id": w_obj.id,
                "start": max(0.0, w_obj.offset),
                "end": min(length, w_obj.offset + w_obj.width),
                "height": min(wall_height - w_obj.sill_height, w_obj.height),
                "sill_height": w_obj.sill_height,
                "obj": w_obj
            })

        openings.sort(key=lambda o: o["start"])

        # Construct solid wall segments
        solid_meshes: List[trimesh.Trimesh] = []
        cur_s = 0.0

        for op in openings:
            op_start = op["start"]
            op_end = op["end"]

            # 1. Solid full-height section before this opening
            if op_start > cur_s + 1e-4:
                mesh = _create_box_mesh(p0, u_vec, n_vec, (cur_s, op_start), w_range, (0.0, wall_height))
                if len(mesh.faces) > 0:
                    solid_meshes.append(mesh)

            # 2. Geometry at the opening span
            if op["type"] == "door":
                # Lintel above door
                door_h = op["height"]
                if wall_height > door_h + 1e-4:
                    lintel = _create_box_mesh(p0, u_vec, n_vec, (op_start, op_end), w_range, (door_h, wall_height))
                    if len(lintel.faces) > 0:
                        solid_meshes.append(lintel)
                # Note: Region (0.0 -> door_h) is hollow/opening!

            elif op["type"] == "window":
                sill_h = op["sill_height"]
                win_h = op["height"]
                # Sill below window
                if sill_h > 1e-4:
                    sill = _create_box_mesh(p0, u_vec, n_vec, (op_start, op_end), w_range, (0.0, sill_h))
                    if len(sill.faces) > 0:
                        solid_meshes.append(sill)
                # Lintel above window
                win_top = sill_h + win_h
                if wall_height > win_top + 1e-4:
                    lintel = _create_box_mesh(p0, u_vec, n_vec, (op_start, op_end), w_range, (win_top, wall_height))
                    if len(lintel.faces) > 0:
                        solid_meshes.append(lintel)
                # Note: Region (sill_h -> win_top) is hollow/opening!

            cur_s = max(cur_s, op_end)

        # 3. Solid full-height section after the last opening
        if length > cur_s + 1e-4:
            mesh = _create_box_mesh(p0, u_vec, n_vec, (cur_s, length), w_range, (0.0, wall_height))
            if len(mesh.faces) > 0:
                solid_meshes.append(mesh)

        # Combine all solid segments into the final wall mesh
        if solid_meshes:
            wall_mesh = trimesh.util.concatenate(solid_meshes)
        else:
            wall_mesh = _create_box_mesh(p0, u_vec, n_vec, (0.0, length), w_range, (0.0, wall_height))

        # Assign wall visual material
        wall_mesh.visual.material = self.wall_mat

        # Build optional accessories (frames, leaf, glass)
        door_mesh_data = []
        window_mesh_data = []

        if build_accessories:
            jamb_th = 0.04
            frame_depth = t * 1.05  # slightly proud of wall face for architectural clarity

            for op in openings:
                op_start = op["start"]
                op_end = op["end"]
                op_w = op_end - op_start

                if op["type"] == "door":
                    door_h = op["height"]
                    fw_range = (-frame_depth / 2.0, frame_depth / 2.0)

                    # Door Frame: left jamb, right jamb, top header
                    left_jamb = _create_box_mesh(p0, u_vec, n_vec, (op_start, op_start + jamb_th), fw_range, (0.0, door_h))
                    right_jamb = _create_box_mesh(p0, u_vec, n_vec, (op_end - jamb_th, op_end), fw_range, (0.0, door_h))
                    top_jamb = _create_box_mesh(p0, u_vec, n_vec, (op_start, op_end), fw_range, (door_h - jamb_th, door_h))
                    
                    frame_parts = [m for m in [left_jamb, right_jamb, top_jamb] if len(m.faces) > 0]
                    frame_mesh = trimesh.util.concatenate(frame_parts) if frame_parts else trimesh.Trimesh()
                    frame_mesh.visual.material = self.door_frame_mat

                    # Door Leaf: slightly recessed, elegant timber panel
                    leaf_th = 0.04
                    leaf_w_range = (-leaf_th / 2.0, leaf_th / 2.0)
                    leaf_mesh = _create_box_mesh(
                        p0, u_vec, n_vec,
                        (op_start + jamb_th, op_end - jamb_th),
                        leaf_w_range,
                        (0.02, door_h - jamb_th)
                    )
                    leaf_mesh.visual.material = self.door_leaf_mat

                    door_mesh_data.append({
                        "id": op["id"],
                        "frame_mesh": frame_mesh,
                        "leaf_mesh": leaf_mesh,
                        "bounds": [op_start, op_end, 0.0, door_h]
                    })

                elif op["type"] == "window":
                    sill_h = op["sill_height"]
                    win_h = op["height"]
                    win_top = sill_h + win_h
                    fw_range = (-frame_depth / 2.0, frame_depth / 2.0)

                    # Window Frame: left, right, bottom, top
                    left_f = _create_box_mesh(p0, u_vec, n_vec, (op_start, op_start + jamb_th), fw_range, (sill_h, win_top))
                    right_f = _create_box_mesh(p0, u_vec, n_vec, (op_end - jamb_th, op_end), fw_range, (sill_h, win_top))
                    bot_f = _create_box_mesh(p0, u_vec, n_vec, (op_start, op_end), fw_range, (sill_h, sill_h + jamb_th))
                    top_f = _create_box_mesh(p0, u_vec, n_vec, (op_start, op_end), fw_range, (win_top - jamb_th, win_top))

                    frame_parts = [m for m in [left_f, right_f, bot_f, top_f] if len(m.faces) > 0]
                    frame_mesh = trimesh.util.concatenate(frame_parts) if frame_parts else trimesh.Trimesh()
                    frame_mesh.visual.material = self.win_frame_mat

                    # Window Glass: thin translucent pane
                    glass_th = 0.012
                    glass_w_range = (-glass_th / 2.0, glass_th / 2.0)
                    glass_mesh = _create_box_mesh(
                        p0, u_vec, n_vec,
                        (op_start + jamb_th, op_end - jamb_th),
                        glass_w_range,
                        (sill_h + jamb_th, win_top - jamb_th)
                    )
                    glass_mesh.visual.material = self.win_glass_mat

                    window_mesh_data.append({
                        "id": op["id"],
                        "frame_mesh": frame_mesh,
                        "glass_mesh": glass_mesh,
                        "bounds": [op_start, op_end, sill_h, win_top]
                    })

        return {
            "wall_id": wall.id,
            "wall_mesh": wall_mesh,
            "door_meshes": door_mesh_data,
            "window_meshes": window_mesh_data,
            "length": length,
            "thickness": t,
            "height": wall_height
        }
