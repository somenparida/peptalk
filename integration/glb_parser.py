import logging
from pathlib import Path
from typing import Dict, Any, List
import numpy as np
import trimesh

log = logging.getLogger(__name__)


def parse_glb_to_scene(glb_path: Path | str) -> Dict[str, Any]:
    """
    Parse a 3D GLB model file into a standardized scene dictionary
    conforming to scene_schema.json.
    Extracts walls, doors, windows, and rooms from 3D mesh extents and names.
    """
    glb_path = Path(glb_path)
    scene_3d = trimesh.load(glb_path)

    walls: List[Dict[str, Any]] = []
    doors: List[Dict[str, Any]] = []
    windows: List[Dict[str, Any]] = []
    rooms: List[Dict[str, Any]] = []

    wall_count = 0
    door_count = 0
    win_count = 0
    room_count = 0

    if isinstance(scene_3d, trimesh.Scene):
        for name, geom in scene_3d.geometry.items():
            if not hasattr(geom, "bounds"):
                continue

            bounds = geom.bounds  # [[min_x, min_y, min_z], [max_x, max_y, max_z]]
            min_pt, max_pt = bounds[0], bounds[1]
            extents = max_pt - min_pt

            # Handle Walls
            if "wall" in name.lower():
                wall_count += 1
                wall_id = f"wall_glb_{wall_count:03d}"

                # Determine line orientation
                if extents[0] >= extents[1]:  # Horizontal wall (along X)
                    start = [round(float(min_pt[0]), 3), round(float((min_pt[1] + max_pt[1]) / 2.0), 3)]
                    end = [round(float(max_pt[0]), 3), round(float((min_pt[1] + max_pt[1]) / 2.0), 3)]
                    thickness = round(float(extents[1]), 3)
                else:  # Vertical wall (along Y)
                    start = [round(float((min_pt[0] + max_pt[0]) / 2.0), 3), round(float(min_pt[1]), 3)]
                    end = [round(float((min_pt[0] + max_pt[0]) / 2.0), 3), round(float(max_pt[2] if extents[1] == 0 else max_pt[1]), 3)]
                    thickness = round(float(extents[0]), 3)

                height = round(float(extents[2]), 3) if extents[2] > 0 else 3.0

                walls.append({
                    "id": wall_id,
                    "start": start,
                    "end": end,
                    "thickness": max(0.05, thickness),
                    "height": max(0.5, height),
                    "source": "detected",
                    "confidence": 0.95,
                })

            # Handle Doors
            elif "door_frame" in name.lower() or "door" in name.lower():
                if "leaf" in name.lower():
                    continue  # Avoid duplicate entries for frame vs leaf
                door_count += 1
                doors.append({
                    "id": f"door_glb_{door_count:03d}",
                    "wall_id": f"wall_glb_{max(1, wall_count):03d}",
                    "position": 0.50,
                    "width": round(float(max(extents[0], extents[1])), 3),
                    "height": round(float(extents[2]), 3) if extents[2] > 0 else 2.10,
                    "source": "detected",
                    "confidence": 0.90,
                })

            # Handle Windows
            elif "window_frame" in name.lower() or "window" in name.lower():
                if "glass" in name.lower():
                    continue
                win_count += 1
                windows.append({
                    "id": f"window_glb_{win_count:03d}",
                    "wall_id": f"wall_glb_{max(1, wall_count):03d}",
                    "position": 0.50,
                    "width": round(float(max(extents[0], extents[1])), 3),
                    "sill_height": round(float(min_pt[2]), 3) if min_pt[2] >= 0 else 0.90,
                    "height": round(float(extents[2]), 3) if extents[2] > 0 else 1.20,
                    "source": "detected",
                    "confidence": 0.90,
                })

            # Handle Rooms / Floors
            elif "floor" in name.lower() or "room" in name.lower():
                if "ceiling" in name.lower():
                    continue
                room_count += 1
                r_min_x, r_min_y = float(min_pt[0]), float(min_pt[1])
                r_max_x, r_max_y = float(max_pt[0]), float(max_pt[1])

                label = name.replace("floor_room_", "").replace("floor_", "")

                rooms.append({
                    "id": f"room_glb_{room_count:03d}",
                    "label": label,
                    "polygon": [
                        [round(r_min_x, 3), round(r_min_y, 3)],
                        [round(r_max_x, 3), round(r_min_y, 3)],
                        [round(r_max_x, 3), round(r_max_y, 3)],
                        [round(r_min_x, 3), round(r_max_y, 3)],
                    ],
                    "source": "detected",
                    "confidence": 0.92,
                })

    # Fallback if GLB had no named mesh parts
    if not walls:
        walls.append({
            "id": "wall_glb_001",
            "start": [0.0, 0.0],
            "end": [5.0, 0.0],
            "thickness": 0.20,
            "height": 3.0,
            "source": "estimated",
            "confidence": 0.50,
        })

    # Extents / units
    units = "meters"
    scene_extents = scene_3d.extents if hasattr(scene_3d, "extents") else [10, 10, 3]

    return {
        "version": "1.0",
        "units": units,
        "source": {"filename": glb_path.name},
        "scale": {
            "value": 1.0,
            "unit": "meters",
            "source": "explicit",
            "confidence": 0.95,
        },
        "walls": walls,
        "doors": doors,
        "windows": windows,
        "rooms": rooms,
    }
