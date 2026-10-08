import os
import math
from pathlib import Path
from typing import Dict, Any
import numpy as np
from PIL import Image

import trimesh


def stub_analyze_floorplan(path: Path | str) -> Dict[str, np.ndarray]:
    """Return dummy 400x300 masks for walls, doors, windows, and floors."""
    h, w = 300, 400
    wall = np.zeros((h, w), dtype=np.uint8)
    wall[20:24, 20:380] = 255
    wall[276:280, 20:380] = 255
    wall[20:280, 20:24] = 255
    wall[20:280, 376:380] = 255

    door = np.zeros_like(wall)
    door[274:282, 150:190] = 255

    window = np.zeros_like(wall)
    window[18:26, 250:320] = 255

    floor = np.zeros_like(wall)
    floor[24:276, 24:376] = 255

    return {
        "wall_mask": wall,
        "door_mask": door,
        "window_mask": window,
        "floor_mask": floor,
    }


def stub_reconstruct_geometry(masks: Dict[str, np.ndarray]) -> Dict[str, Any]:
    """Return a valid scene dictionary in PIXEL units (scale applied later)."""
    return {
        "version": "1.0",
        "units": "pixels",
        "source": {"filename": "stub_input.png"},
        "scale": {
            "value": 1.0,
            "unit": "pixels",
            "source": "estimated",
            "confidence": 0.5,
        },
        "walls": [
            {
                "id": "wall_001",
                "start": [22.0, 22.0],
                "end": [378.0, 22.0],
                "thickness": 4.0,
                "height": 3.0,
                "source": "detected",
                "confidence": 0.95,
            },
            {
                "id": "wall_002",
                "start": [378.0, 22.0],
                "end": [378.0, 278.0],
                "thickness": 4.0,
                "height": 3.0,
                "source": "detected",
                "confidence": 0.95,
            },
            {
                "id": "wall_003",
                "start": [378.0, 278.0],
                "end": [22.0, 278.0],
                "thickness": 4.0,
                "height": 3.0,
                "source": "detected",
                "confidence": 0.95,
            },
            {
                "id": "wall_004",
                "start": [22.0, 278.0],
                "end": [22.0, 22.0],
                "thickness": 4.0,
                "height": 3.0,
                "source": "detected",
                "confidence": 0.95,
            },
        ],
        "doors": [
            {
                "id": "door_001",
                "wall_id": "wall_003",
                "position": 0.45,
                "width": 40.0,
                "height": 2.1,
                "source": "detected",
                "confidence": 0.90,
            }
        ],
        "windows": [
            {
                "id": "window_001",
                "wall_id": "wall_001",
                "position": 0.65,
                "width": 70.0,
                "sill_height": 0.9,
                "height": 1.2,
                "source": "detected",
                "confidence": 0.90,
            }
        ],
        "rooms": [
            {
                "id": "room_001",
                "label": "main_room",
                "polygon": [
                    [24.0, 24.0],
                    [376.0, 24.0],
                    [376.0, 276.0],
                    [24.0, 276.0],
                ],
                "source": "inferred",
                "confidence": 0.92,
            }
        ],
    }


def stub_generate_3d(scene_data: Dict[str, Any], out_path: Path | str) -> str:
    """Extrude walls with trimesh and export a GLB model."""
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    meshes = []
    walls = scene_data.get("walls", [])

    for wall in walls:
        p1 = wall["start"]
        p2 = wall["end"]
        height = float(wall.get("height", 3.0))
        thickness = float(wall.get("thickness", 0.20))

        dx = p2[0] - p1[0]
        dy = p2[1] - p1[1]
        length = math.hypot(dx, dy)
        if length <= 1e-6:
            continue

        angle = math.atan2(dy, dx)
        center_x = (p1[0] + p2[0]) / 2.0
        center_y = (p1[1] + p2[1]) / 2.0
        center_z = height / 2.0

        # Create box centered at origin: extents = [length, thickness, height]
        box = trimesh.creation.box(extents=[length, thickness, height])

        # Rotation matrix around Z
        matrix = trimesh.transformations.rotation_matrix(angle, [0, 0, 1])
        # Translation matrix
        matrix[0:3, 3] = [center_x, center_y, center_z]

        box.apply_transform(matrix)
        meshes.append(box)

    if not meshes:
        # Fallback box if no walls exist
        box = trimesh.creation.box(extents=[1.0, 1.0, 1.0])
        meshes.append(box)

    # Combine meshes into scene and export GLB
    scene_3d = trimesh.Scene(meshes)
    glb_bytes = scene_3d.export(file_type="glb")

    with open(out_path, "wb") as f:
        f.write(glb_bytes)

    return str(out_path)
