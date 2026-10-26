"""Procedural 3D solid wall reconstruction with exact opening cutouts and lintels."""

from __future__ import annotations

from typing import List, Tuple

import trimesh

from src.builder.mesh_utils import create_transformed_box
from src.config import CONFIG
from src.models import OpeningType, WallEdge


class WallMeshBuilder:
    """
    Constructs watertight 3D solid wall geometry featuring exact rectangular cutouts
    for doors and windows, complete with above-opening lintels and below-window sills.
    """

    def __init__(self) -> None:
        pass

    def build_wall_mesh(self, wall: WallEdge) -> Tuple[trimesh.Trimesh, trimesh.Trimesh]:
        """
        Builds 3D mesh for a single wall segment.
        Returns: (wall_body_mesh, lintel_mesh).
        """
        L = wall.length
        T = wall.thickness
        H = wall.height
        half_t = 0.5 * T

        wall_boxes: List[trimesh.Trimesh] = []
        lintel_boxes: List[trimesh.Trimesh] = []

        # 1. Solid wall segments (full floor-to-ceiling height)
        for s0, s1 in wall.get_solid_intervals():
            box = create_transformed_box(
                s0=s0,
                s1=s1,
                t0=-half_t,
                t1=half_t,
                z0=0.0,
                z1=H,
                start=wall.start,
                direction=wall.direction,
                normal=wall.normal,
                color=CONFIG.COLOR_WALL,
            )
            if not box.is_empty:
                wall_boxes.append(box)

        # 2. Opening regions: Cutouts, Sills, and Lintels
        for op in wall.openings:
            s0 = op.start_dist
            s1 = op.end_dist

            if op.opening_type == OpeningType.DOOR:
                # Lintel above door from door top to ceiling
                if op.height < H:
                    lintel_box = create_transformed_box(
                        s0=s0,
                        s1=s1,
                        t0=-half_t,
                        t1=half_t,
                        z0=op.height,
                        z1=H,
                        start=wall.start,
                        direction=wall.direction,
                        normal=wall.normal,
                        color=CONFIG.COLOR_LINTEL,
                    )
                    if not lintel_box.is_empty:
                        lintel_boxes.append(lintel_box)

            elif op.opening_type == OpeningType.WINDOW:
                # Wall below window sill terminates at underside of stone sill
                sill_wall_top = max(0.0, op.sill_height - CONFIG.WINDOW_SILL_THICKNESS)
                if sill_wall_top > 1e-4:
                    sill_wall = create_transformed_box(
                        s0=s0,
                        s1=s1,
                        t0=-half_t,
                        t1=half_t,
                        z0=0.0,
                        z1=sill_wall_top,
                        start=wall.start,
                        direction=wall.direction,
                        normal=wall.normal,
                        color=CONFIG.COLOR_WALL,
                    )
                    if not sill_wall.is_empty:
                        wall_boxes.append(sill_wall)

                # Lintel above window
                win_top = op.sill_height + op.height
                if win_top < H:
                    lintel_box = create_transformed_box(
                        s0=s0,
                        s1=s1,
                        t0=-half_t,
                        t1=half_t,
                        z0=win_top,
                        z1=H,
                        start=wall.start,
                        direction=wall.direction,
                        normal=wall.normal,
                        color=CONFIG.COLOR_LINTEL,
                    )
                    if not lintel_box.is_empty:
                        lintel_boxes.append(lintel_box)

        # Concatenate meshes
        wall_mesh = trimesh.util.concatenate(wall_boxes) if wall_boxes else trimesh.Trimesh()
        lintel_mesh = trimesh.util.concatenate(lintel_boxes) if lintel_boxes else trimesh.Trimesh()

        return wall_mesh, lintel_mesh

    def build_all_walls(
        self, walls: List[WallEdge]
    ) -> Tuple[trimesh.Trimesh, trimesh.Trimesh]:
        """Builds all wall bodies and lintels."""
        all_walls: List[trimesh.Trimesh] = []
        all_lintels: List[trimesh.Trimesh] = []

        for w in walls:
            w_mesh, l_mesh = self.build_wall_mesh(w)
            if not w_mesh.is_empty:
                all_walls.append(w_mesh)
            if not l_mesh.is_empty:
                all_lintels.append(l_mesh)

        combined_walls = trimesh.util.concatenate(all_walls) if all_walls else trimesh.Trimesh()
        combined_lintels = trimesh.util.concatenate(all_lintels) if all_lintels else trimesh.Trimesh()

        return combined_walls, combined_lintels
