"""
Structured Scene Graph internal representation for Member 2.

Maintains a hierarchical graph of architectural entities with full provenance:
source IDs, 2D coordinates, 3D dimensions, materials, and spatial relationships.
"""

from __future__ import annotations

from typing import Dict, Any, List, Optional
import numpy as np
import trimesh

from src.schema import SceneSpecification, Wall, Door, Window, Room
from src.geometry.wall_builder import WallMeshBuilder
from src.geometry.room_builder import RoomMeshBuilder


class SceneNode:
    """Represents a discrete architectural 3D entity in the scene graph."""

    def __init__(
        self,
        node_id: str,
        name: str,
        node_type: str,
        source_id: str,
        mesh: Optional[trimesh.Trimesh] = None,
        source_coordinates: Optional[Any] = None,
        dimensions: Optional[Dict[str, float]] = None,
        relationships: Optional[Dict[str, Any]] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ):
        self.node_id = node_id
        self.name = name
        self.node_type = node_type  # 'wall', 'floor', 'ceiling', 'door_leaf', 'door_frame', etc.
        self.source_id = source_id
        self.mesh = mesh
        self.source_coordinates = source_coordinates or {}
        self.dimensions = dimensions or {}
        self.relationships = relationships or {}
        self.metadata = metadata or {}

    @property
    def bounding_box_3d(self) -> Optional[List[float]]:
        if self.mesh is not None and len(self.mesh.vertices) > 0:
            bounds = self.mesh.bounds
            return [
                float(bounds[0][0]), float(bounds[0][1]), float(bounds[0][2]),
                float(bounds[1][0]), float(bounds[1][1]), float(bounds[1][2]),
            ]
        return None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "node_id": self.node_id,
            "name": self.name,
            "type": self.node_type,
            "source_id": self.source_id,
            "source_coordinates": self.source_coordinates,
            "dimensions": self.dimensions,
            "relationships": self.relationships,
            "bounding_box_3d": self.bounding_box_3d,
            "metadata": self.metadata,
        }


class SceneGraph:
    """Hierarchical structured scene containing all architectural entities."""

    def __init__(self, spec: Optional[SceneSpecification] = None):
        self.spec = spec
        self.nodes: Dict[str, SceneNode] = {}
        self.root_name = "Scene_Root"

    @classmethod
    def from_specification(
        cls,
        spec: SceneSpecification,
        build_accessories: bool = True,
        solid_slabs: bool = True
    ) -> SceneGraph:
        """Constructs a fully populated SceneGraph from a SceneSpecification."""
        sg = cls(spec=spec)
        wall_builder = WallMeshBuilder(default_wall_height=spec.wall_height)
        room_builder = RoomMeshBuilder(default_wall_height=spec.wall_height)

        # 1. Map openings by wall_id
        wall_doors: Dict[str, List[Door]] = {w.id: [] for w in spec.walls}
        for d in spec.doors:
            if d.wall_id in wall_doors:
                wall_doors[d.wall_id].append(d)

        wall_windows: Dict[str, List[Window]] = {w.id: [] for w in spec.walls}
        for win in spec.windows:
            if win.wall_id in wall_windows:
                wall_windows[win.wall_id].append(win)

        # 2. Detect shared walls across rooms
        shared_walls_map = RoomMeshBuilder.detect_shared_walls(spec.walls, spec.rooms)

        # 3. Generate Walls & Openings
        for wall in spec.walls:
            w_res = wall_builder.build_wall_with_openings(
                wall=wall,
                doors=wall_doors[wall.id],
                windows=wall_windows[wall.id],
                build_accessories=build_accessories
            )

            # Register Wall Node
            w_node = SceneNode(
                node_id=f"wall_{wall.id}",
                name=f"Wall {wall.id}",
                node_type="wall",
                source_id=wall.id,
                mesh=w_res["wall_mesh"],
                source_coordinates={"start": wall.start, "end": wall.end},
                dimensions={
                    "length_m": round(w_res["length"], 4),
                    "thickness_m": round(w_res["thickness"], 4),
                    "height_m": round(w_res["height"], 4),
                },
                relationships={
                    "bordering_rooms": shared_walls_map.get(wall.id, []),
                    "door_ids": [d.id for d in wall_doors[wall.id]],
                    "window_ids": [win.id for win in wall_windows[wall.id]],
                },
                metadata={"is_shared_wall": len(shared_walls_map.get(wall.id, [])) >= 2}
            )
            sg.nodes[w_node.node_id] = w_node

            # Register Door Accessory Nodes
            for d_info in w_res["door_meshes"]:
                d_id = d_info["id"]
                matching_door = next((d for d in spec.doors if d.id == d_id), None)
                d_dims = {
                    "width_m": matching_door.width if matching_door else 0.9,
                    "height_m": matching_door.height if matching_door else 2.1,
                    "offset_m": matching_door.offset if matching_door else 0.0,
                }
                
                if len(d_info["frame_mesh"].faces) > 0:
                    df_node = SceneNode(
                        node_id=f"door_frame_{d_id}",
                        name=f"Door Frame {d_id}",
                        node_type="door_frame",
                        source_id=d_id,
                        mesh=d_info["frame_mesh"],
                        dimensions=d_dims,
                        relationships={"wall_id": wall.id}
                    )
                    sg.nodes[df_node.node_id] = df_node

                if len(d_info["leaf_mesh"].faces) > 0:
                    dl_node = SceneNode(
                        node_id=f"door_leaf_{d_id}",
                        name=f"Door Leaf {d_id}",
                        node_type="door_leaf",
                        source_id=d_id,
                        mesh=d_info["leaf_mesh"],
                        dimensions=d_dims,
                        relationships={"wall_id": wall.id}
                    )
                    sg.nodes[dl_node.node_id] = dl_node

            # Register Window Accessory Nodes
            for win_info in w_res["window_meshes"]:
                win_id = win_info["id"]
                matching_win = next((w for w in spec.windows if w.id == win_id), None)
                win_dims = {
                    "width_m": matching_win.width if matching_win else 1.2,
                    "height_m": matching_win.height if matching_win else 1.2,
                    "sill_height_m": matching_win.sill_height if matching_win else 0.9,
                    "offset_m": matching_win.offset if matching_win else 0.0,
                }

                if len(win_info["frame_mesh"].faces) > 0:
                    wf_node = SceneNode(
                        node_id=f"window_frame_{win_id}",
                        name=f"Window Frame {win_id}",
                        node_type="window_frame",
                        source_id=win_id,
                        mesh=win_info["frame_mesh"],
                        dimensions=win_dims,
                        relationships={"wall_id": wall.id}
                    )
                    sg.nodes[wf_node.node_id] = wf_node

                if len(win_info["glass_mesh"].faces) > 0:
                    wg_node = SceneNode(
                        node_id=f"window_glass_{win_id}",
                        name=f"Window Glass {win_id}",
                        node_type="window_glass",
                        source_id=win_id,
                        mesh=win_info["glass_mesh"],
                        dimensions=win_dims,
                        relationships={"wall_id": wall.id}
                    )
                    sg.nodes[wg_node.node_id] = wg_node

        # 4. Generate Rooms (Floors & Ceilings)
        for room in spec.rooms:
            r_res = room_builder.build_room(room=room, as_solid_slab=solid_slabs)

            # Floor Node
            f_node = SceneNode(
                node_id=f"floor_{room.id}",
                name=f"Floor ({room.name or room.id})",
                node_type="floor",
                source_id=room.id,
                mesh=r_res["floor_mesh"],
                source_coordinates={"polygon": room.polygon},
                dimensions={
                    "area_m2": round(r_res["area"], 4),
                    "perimeter_m": round(r_res["perimeter"], 4)
                },
                relationships={"room_id": room.id}
            )
            sg.nodes[f_node.node_id] = f_node

            # Ceiling Node
            c_node = SceneNode(
                node_id=f"ceiling_{room.id}",
                name=f"Ceiling ({room.name or room.id})",
                node_type="ceiling",
                source_id=room.id,
                mesh=r_res["ceiling_mesh"],
                source_coordinates={"polygon": room.polygon},
                dimensions={
                    "area_m2": round(r_res["area"], 4),
                    "elevation_z_m": round(r_res["wall_height"], 4)
                },
                relationships={"room_id": room.id}
            )
            sg.nodes[c_node.node_id] = c_node

        return sg

    def to_trimesh_scene(self) -> trimesh.Scene:
        """Converts the SceneGraph into a trimesh.Scene suitable for rendering and export."""
        scene = trimesh.Scene()
        for node_id, node in self.nodes.items():
            if node.mesh is not None and len(node.mesh.faces) > 0:
                # Add mesh to scene with node identifier
                scene.add_geometry(
                    geometry=node.mesh,
                    node_name=node_id,
                    geom_name=node_id,
                )
        return scene

    def get_inspection_metadata(self) -> Dict[str, Any]:
        """Provides full metadata dictionary for visual debug inspection in the 3D viewer."""
        return {
            node_id: node.to_dict()
            for node_id, node in self.nodes.items()
        }
