"""Assembly of 3D architectural scene from procedural components."""

from __future__ import annotations

from typing import Any, Dict

import trimesh

from src.builder.opening_builder import OpeningMeshBuilder
from src.builder.slab_builder import SlabMeshBuilder
from src.builder.wall_builder import WallMeshBuilder
from src.config import CONFIG
from src.models import FloorPlan


class ArchitecturalSceneBuilder:
    """
    Assembles complete procedural 3D architectural scene from floor plan definition.
    Organizes geometry into semantic nodes for downstream rendering and inspection.
    """

    def __init__(self) -> None:
        self.wall_builder = WallMeshBuilder()
        self.opening_builder = OpeningMeshBuilder()
        self.slab_builder = SlabMeshBuilder()

    def build_scene(self, floor_plan: FloorPlan) -> trimesh.Scene:
        """Constructs trimesh.Scene containing all architectural submeshes."""
        scene = trimesh.Scene()

        # 1. Walls and Lintels
        walls_mesh, lintels_mesh = self.wall_builder.build_all_walls(floor_plan.walls)
        if not walls_mesh.is_empty:
            scene.add_geometry(walls_mesh, node_name="Walls", geom_name="Walls")
        if not lintels_mesh.is_empty:
            scene.add_geometry(lintels_mesh, node_name="Lintels", geom_name="Lintels")

        # 2. Doors and Windows
        openings_dict = self.opening_builder.build_all_openings(floor_plan.walls)
        if not openings_dict["door_frames"].is_empty:
            scene.add_geometry(
                openings_dict["door_frames"], node_name="DoorFrames", geom_name="DoorFrames"
            )
        if not openings_dict["door_leaves"].is_empty:
            scene.add_geometry(
                openings_dict["door_leaves"], node_name="DoorLeaves", geom_name="DoorLeaves"
            )
        if "door_hardware" in openings_dict and not openings_dict["door_hardware"].is_empty:
            scene.add_geometry(
                openings_dict["door_hardware"], node_name="DoorHardware", geom_name="DoorHardware"
            )
        if not openings_dict["window_frames"].is_empty:
            scene.add_geometry(
                openings_dict["window_frames"], node_name="WindowFrames", geom_name="WindowFrames"
            )
        if "window_mullions" in openings_dict and not openings_dict["window_mullions"].is_empty:
            scene.add_geometry(
                openings_dict["window_mullions"], node_name="WindowMullions", geom_name="WindowMullions"
            )
        if not openings_dict["window_glasses"].is_empty:
            scene.add_geometry(
                openings_dict["window_glasses"], node_name="WindowGlasses", geom_name="WindowGlasses"
            )
        if not openings_dict["window_sills"].is_empty:
            scene.add_geometry(
                openings_dict["window_sills"], node_name="WindowSills", geom_name="WindowSills"
            )

        # 3. Floors, Ceilings, and Plinth
        if floor_plan.rooms:
            floors_mesh = self.slab_builder.build_room_floors(floor_plan.rooms)
            if not floors_mesh.is_empty:
                scene.add_geometry(floors_mesh, node_name="Floors", geom_name="Floors")

            ceilings_mesh = self.slab_builder.build_ceilings(floor_plan.rooms)
            if not ceilings_mesh.is_empty:
                scene.add_geometry(ceilings_mesh, node_name="Ceilings", geom_name="Ceilings")

            plinth_mesh = self.slab_builder.build_site_plinth(floor_plan.rooms)
            if not plinth_mesh.is_empty:
                scene.add_geometry(plinth_mesh, node_name="Plinth", geom_name="Plinth")

        # Attach architectural metadata
        scene.metadata.update({
            "total_floor_area_sq_m": floor_plan.total_area,
            "total_wall_length_m": floor_plan.total_wall_length,
            "wall_count": len(floor_plan.walls),
            "room_count": len(floor_plan.rooms),
            "openings": floor_plan.opening_counts,
            "rooms": [r.to_dict() for r in floor_plan.rooms],
        })

        return scene
