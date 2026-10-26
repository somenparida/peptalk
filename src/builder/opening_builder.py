"""Procedural 3D door frames, leaves with panel detailing, brass handles, window frames, mullions, glass panes, and architectural sills."""

from __future__ import annotations

from typing import Dict, List, Tuple

import trimesh

from src.builder.mesh_utils import create_transformed_box
from src.config import CONFIG
from src.models import OpeningInterval, OpeningType, WallEdge


class OpeningMeshBuilder:
    """
    Constructs detailed architectural components for doors and windows:
    - 3D door frames (jambs + casing header)
    - Wood door leaves with recessed panel profiling
    - 3D architectural door hardware (escutcheon plates and lever handles in brass)
    - 3D window frames (dark anodized aluminum)
    - Window divided-lite mullions & transom crossbars
    - Realistic tinted glass panes
    - Protruding stone window sills with drip overhang
    """

    def build_door_mesh(
        self, wall: WallEdge, op: OpeningInterval
    ) -> Dict[str, trimesh.Trimesh]:
        """Builds detailed door frame, paneled leaf, and brass hardware."""
        s0, s1 = op.start_dist, op.end_dist
        frame_t = CONFIG.DOOR_FRAME_THICKNESS
        frame_d = CONFIG.DOOR_FRAME_DEPTH
        half_fd = 0.5 * frame_d

        frame_parts: List[trimesh.Trimesh] = []

        # 1. Door Frame: Left jamb, right jamb, and top header
        frame_parts.append(
            create_transformed_box(
                s0=s0,
                s1=s0 + frame_t,
                t0=-half_fd,
                t1=half_fd,
                z0=0.0,
                z1=op.height,
                start=wall.start,
                direction=wall.direction,
                normal=wall.normal,
                color=CONFIG.COLOR_DOOR_FRAME,
            )
        )
        frame_parts.append(
            create_transformed_box(
                s0=s1 - frame_t,
                s1=s1,
                t0=-half_fd,
                t1=half_fd,
                z0=0.0,
                z1=op.height,
                start=wall.start,
                direction=wall.direction,
                normal=wall.normal,
                color=CONFIG.COLOR_DOOR_FRAME,
            )
        )
        # Top casing header spans flush between jambs without overlapping corner volumes
        frame_parts.append(
            create_transformed_box(
                s0=s0 + frame_t,
                s1=s1 - frame_t,
                t0=-half_fd,
                t1=half_fd,
                z0=op.height - frame_t,
                z1=op.height,
                start=wall.start,
                direction=wall.direction,
                normal=wall.normal,
                color=CONFIG.COLOR_DOOR_FRAME,
            )
        )

        frame_mesh = trimesh.util.concatenate([m for m in frame_parts if not m.is_empty])

        # 2. Door Leaf: Rich wood stile-and-rail with recessed panels
        leaf_parts: List[trimesh.Trimesh] = []
        leaf_s0 = s0 + frame_t + 0.005
        leaf_s1 = s1 - frame_t - 0.005
        leaf_w = leaf_s1 - leaf_s0
        leaf_h = op.height - frame_t - 0.005
        half_leaf_t = 0.022  # 44mm solid core door

        # Main door leaf body
        leaf_parts.append(
            create_transformed_box(
                s0=leaf_s0,
                s1=leaf_s1,
                t0=-half_leaf_t,
                t1=half_leaf_t,
                z0=0.015,
                z1=leaf_h,
                start=wall.start,
                direction=wall.direction,
                normal=wall.normal,
                color=CONFIG.COLOR_DOOR_LEAF,
            )
        )

        # Architectural inset panels for visual depth
        margin_s = 0.10 * leaf_w
        p_s0 = leaf_s0 + margin_s
        p_s1 = leaf_s1 - margin_s

        # Lower inset panel (z: 0.15m to 0.85m)
        leaf_parts.append(
            create_transformed_box(
                s0=p_s0,
                s1=p_s1,
                t0=-(half_leaf_t + 0.004),
                t1=(half_leaf_t + 0.004),
                z0=0.15,
                z1=0.85,
                start=wall.start,
                direction=wall.direction,
                normal=wall.normal,
                color=CONFIG.COLOR_DOOR_PANEL,
            )
        )
        # Upper inset panel (z: 1.15m to 1.85m)
        leaf_parts.append(
            create_transformed_box(
                s0=p_s0,
                s1=p_s1,
                t0=-(half_leaf_t + 0.004),
                t1=(half_leaf_t + 0.004),
                z0=1.15,
                z1=1.85,
                start=wall.start,
                direction=wall.direction,
                normal=wall.normal,
                color=CONFIG.COLOR_DOOR_PANEL,
            )
        )

        leaf_mesh = trimesh.util.concatenate([m for m in leaf_parts if not m.is_empty])

        # 3. Door Hardware: Brass Escutcheon Backplates, Spindles, and Lever Handles
        hardware_parts: List[trimesh.Trimesh] = []
        handle_z = 0.98  # standard height in meters
        lever_len = 0.10
        spindle_half_w = 0.012

        # Respect hinge metadata: hinge can be "start" or "end". Default is "start".
        hinge_side = str(op.metadata.get("hinge", "start")).lower().strip()
        if hinge_side == "end":
            # Hinge at leaf_s1; latch and handle are near leaf_s0
            h_s0 = leaf_s0 + 0.04
            h_s1 = leaf_s0 + 0.09
            handle_s0 = h_s1
            handle_s1 = h_s1 + lever_len
            spindle_s0 = h_s1 - spindle_half_w
            spindle_s1 = h_s1 + spindle_half_w
        else:
            # Default: hinge at leaf_s0; latch and handle are near leaf_s1
            h_s0 = leaf_s1 - 0.09
            h_s1 = leaf_s1 - 0.04
            handle_s0 = h_s0 - lever_len
            handle_s1 = h_s0
            spindle_s0 = h_s0 - spindle_half_w
            spindle_s1 = h_s0 + spindle_half_w

        plate_half_h = 0.08
        plate_thickness = 0.008
        handle_t_offset = 0.040
        handle_t_thickness = 0.015

        # Backplates on both front (+t) and back (-t) faces
        hardware_parts.append(
            create_transformed_box(
                s0=h_s0,
                s1=h_s1,
                t0=half_leaf_t,
                t1=half_leaf_t + plate_thickness,
                z0=handle_z - plate_half_h,
                z1=handle_z + plate_half_h,
                start=wall.start,
                direction=wall.direction,
                normal=wall.normal,
                color=CONFIG.COLOR_DOOR_HANDLE,
            )
        )
        hardware_parts.append(
            create_transformed_box(
                s0=h_s0,
                s1=h_s1,
                t0=-(half_leaf_t + plate_thickness),
                t1=-half_leaf_t,
                z0=handle_z - plate_half_h,
                z1=handle_z + plate_half_h,
                start=wall.start,
                direction=wall.direction,
                normal=wall.normal,
                color=CONFIG.COLOR_DOOR_HANDLE,
            )
        )

        # Connecting spindles/shanks: physically bridge backplate to lever handle (no air gap)
        hardware_parts.append(
            create_transformed_box(
                s0=spindle_s0,
                s1=spindle_s1,
                t0=half_leaf_t + plate_thickness,
                t1=half_leaf_t + handle_t_offset,
                z0=handle_z - 0.01,
                z1=handle_z + 0.01,
                start=wall.start,
                direction=wall.direction,
                normal=wall.normal,
                color=CONFIG.COLOR_DOOR_HANDLE,
            )
        )
        hardware_parts.append(
            create_transformed_box(
                s0=spindle_s0,
                s1=spindle_s1,
                t0=-(half_leaf_t + handle_t_offset),
                t1=-(half_leaf_t + plate_thickness),
                z0=handle_z - 0.01,
                z1=handle_z + 0.01,
                start=wall.start,
                direction=wall.direction,
                normal=wall.normal,
                color=CONFIG.COLOR_DOOR_HANDLE,
            )
        )

        # Lever handles pointing inward along door face
        hardware_parts.append(
            create_transformed_box(
                s0=handle_s0,
                s1=handle_s1,
                t0=half_leaf_t + handle_t_offset,
                t1=half_leaf_t + handle_t_offset + handle_t_thickness,
                z0=handle_z - 0.01,
                z1=handle_z + 0.01,
                start=wall.start,
                direction=wall.direction,
                normal=wall.normal,
                color=CONFIG.COLOR_DOOR_HANDLE,
            )
        )
        hardware_parts.append(
            create_transformed_box(
                s0=handle_s0,
                s1=handle_s1,
                t0=-(half_leaf_t + handle_t_offset + handle_t_thickness),
                t1=-(half_leaf_t + handle_t_offset),
                z0=handle_z - 0.01,
                z1=handle_z + 0.01,
                start=wall.start,
                direction=wall.direction,
                normal=wall.normal,
                color=CONFIG.COLOR_DOOR_HANDLE,
            )
        )

        hardware_mesh = (
            trimesh.util.concatenate([m for m in hardware_parts if not m.is_empty])
            if hardware_parts
            else trimesh.Trimesh()
        )

        return {
            "door_frame": frame_mesh,
            "door_leaf": leaf_mesh,
            "door_hardware": hardware_mesh,
        }

    def build_window_mesh(
        self, wall: WallEdge, op: OpeningInterval
    ) -> Dict[str, trimesh.Trimesh]:
        """Builds window frame, divided-lite mullions, glass pane, and stone sill."""
        s0, s1 = op.start_dist, op.end_dist
        frame_t = CONFIG.WINDOW_FRAME_THICKNESS
        half_wt = 0.5 * (wall.thickness + 0.02)
        z_bottom = op.sill_height
        z_top = op.sill_height + op.height

        frame_parts: List[trimesh.Trimesh] = []

        # 1. Outer Perimeter Frame (Jambs, Header, Sill Bar)
        frame_parts.append(
            create_transformed_box(
                s0=s0,
                s1=s0 + frame_t,
                t0=-half_wt,
                t1=half_wt,
                z0=z_bottom,
                z1=z_top,
                start=wall.start,
                direction=wall.direction,
                normal=wall.normal,
                color=CONFIG.COLOR_WINDOW_FRAME,
            )
        )
        frame_parts.append(
            create_transformed_box(
                s0=s1 - frame_t,
                s1=s1,
                t0=-half_wt,
                t1=half_wt,
                z0=z_bottom,
                z1=z_top,
                start=wall.start,
                direction=wall.direction,
                normal=wall.normal,
                color=CONFIG.COLOR_WINDOW_FRAME,
            )
        )
        frame_parts.append(
            create_transformed_box(
                s0=s0,
                s1=s1,
                t0=-half_wt,
                t1=half_wt,
                z0=z_top - frame_t,
                z1=z_top,
                start=wall.start,
                direction=wall.direction,
                normal=wall.normal,
                color=CONFIG.COLOR_WINDOW_FRAME,
            )
        )
        frame_parts.append(
            create_transformed_box(
                s0=s0,
                s1=s1,
                t0=-half_wt,
                t1=half_wt,
                z0=z_bottom,
                z1=z_bottom + frame_t,
                start=wall.start,
                direction=wall.direction,
                normal=wall.normal,
                color=CONFIG.COLOR_WINDOW_FRAME,
            )
        )

        frame_mesh = trimesh.util.concatenate([m for m in frame_parts if not m.is_empty])

        # 2. Divided-Lite Architectural Mullions & Transoms
        mullion_parts: List[trimesh.Trimesh] = []
        half_mt = 0.016
        # Vertical mullion down the middle
        s_mid = 0.5 * (s0 + s1)
        mullion_parts.append(
            create_transformed_box(
                s0=s_mid - half_mt,
                s1=s_mid + half_mt,
                t0=-(half_wt - 0.01),
                t1=(half_wt - 0.01),
                z0=z_bottom + frame_t,
                z1=z_top - frame_t,
                start=wall.start,
                direction=wall.direction,
                normal=wall.normal,
                color=CONFIG.COLOR_WINDOW_MULLION,
            )
        )

        # Horizontal transom crossbar at 65% height
        z_transom = z_bottom + 0.65 * op.height
        mullion_parts.append(
            create_transformed_box(
                s0=s0 + frame_t,
                s1=s1 - frame_t,
                t0=-(half_wt - 0.01),
                t1=(half_wt - 0.01),
                z0=z_transom - half_mt,
                z1=z_transom + half_mt,
                start=wall.start,
                direction=wall.direction,
                normal=wall.normal,
                color=CONFIG.COLOR_WINDOW_MULLION,
            )
        )

        mullion_mesh = (
            trimesh.util.concatenate([m for m in mullion_parts if not m.is_empty])
            if mullion_parts
            else trimesh.Trimesh()
        )

        # 3. Transparent Tinted Glass Panes
        glass_mesh = create_transformed_box(
            s0=s0 + frame_t,
            s1=s1 - frame_t,
            t0=-0.006,
            t1=0.006,
            z0=z_bottom + frame_t,
            z1=z_top - frame_t,
            start=wall.start,
            direction=wall.direction,
            normal=wall.normal,
            color=CONFIG.COLOR_WINDOW_GLASS,
        )

        # 4. Protruding Architectural Stone Sill
        sill_overhang = CONFIG.WINDOW_SILL_OVERHANG + 0.02
        sill_z0 = max(0.0, z_bottom - CONFIG.WINDOW_SILL_THICKNESS)
        sill_z1 = z_bottom
        sill_mesh = (
            create_transformed_box(
                s0=s0 - 0.06,
                s1=s1 + 0.06,
                t0=-(0.5 * wall.thickness + sill_overhang),
                t1=(0.5 * wall.thickness + sill_overhang),
                z0=sill_z0,
                z1=sill_z1,
                start=wall.start,
                direction=wall.direction,
                normal=wall.normal,
                color=CONFIG.COLOR_WINDOW_SILL,
            )
            if sill_z1 > sill_z0 + 1e-4
            else trimesh.Trimesh()
        )

        return {
            "window_frame": frame_mesh,
            "window_mullions": mullion_mesh,
            "window_glass": glass_mesh,
            "window_sill": sill_mesh,
        }

    def build_all_openings(
        self, walls: List[WallEdge]
    ) -> Dict[str, trimesh.Trimesh]:
        """Builds all opening submeshes across all walls."""
        categories: Dict[str, List[trimesh.Trimesh]] = {
            "door_frames": [],
            "door_leaves": [],
            "door_hardware": [],
            "window_frames": [],
            "window_mullions": [],
            "window_glasses": [],
            "window_sills": [],
        }

        for wall in walls:
            for op in wall.openings:
                if op.opening_type == OpeningType.DOOR:
                    door_dict = self.build_door_mesh(wall, op)
                    if not door_dict["door_frame"].is_empty:
                        categories["door_frames"].append(door_dict["door_frame"])
                    if not door_dict["door_leaf"].is_empty:
                        categories["door_leaves"].append(door_dict["door_leaf"])
                    if "door_hardware" in door_dict and not door_dict["door_hardware"].is_empty:
                        categories["door_hardware"].append(door_dict["door_hardware"])

                elif op.opening_type == OpeningType.WINDOW:
                    win_dict = self.build_window_mesh(wall, op)
                    if not win_dict["window_frame"].is_empty:
                        categories["window_frames"].append(win_dict["window_frame"])
                    if "window_mullions" in win_dict and not win_dict["window_mullions"].is_empty:
                        categories["window_mullions"].append(win_dict["window_mullions"])
                    if not win_dict["window_glass"].is_empty:
                        categories["window_glasses"].append(win_dict["window_glass"])
                    if not win_dict["window_sill"].is_empty:
                        categories["window_sills"].append(win_dict["window_sill"])

        result = {}
        for key, meshes in categories.items():
            result[key] = trimesh.util.concatenate(meshes) if meshes else trimesh.Trimesh()

        return result
