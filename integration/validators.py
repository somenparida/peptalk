import os
import math
from pathlib import Path
from typing import Tuple, List, Dict, Any
import numpy as np
from PIL import Image
import pymupdf  # PyMuPDF
from shapely.geometry import Polygon, Point, LineString

from .schemas import Scene
from .config import (
    DISCONNECTED_WALL_TOL_FACTOR,
    SANITY_MIN_WALL_THICKNESS,
    SANITY_MAX_WALL_THICKNESS,
)


def validate_input(path: Path | str) -> Tuple[Path, List[str]]:
    """
    Validate input floor plan file.
    - Check file existence and extension (.png, .jpg, .jpeg, .pdf)
    - Open with Pillow
    - If PDF, rasterize page 1 at 200 DPI with PyMuPDF
    - Warn if resolution is low (< 400px on shorter side)
    """
    input_path = Path(path).resolve()
    warnings = []

    if not input_path.exists():
        raise FileNotFoundError(f"Input file not found: {input_path}")

    ext = input_path.suffix.lower()
    if ext not in [".png", ".jpg", ".jpeg", ".pdf", ".glb", ".json"]:
        raise ValueError(f"Unsupported file format '{ext}'. Allowed: .png, .jpg, .jpeg, .pdf, .glb, .json")

    usable_path = input_path

    if ext == ".glb":
        warnings.append("Input is a pre-generated 3D GLB model file.")
        return usable_path, warnings

    if ext == ".json":
        warnings.append("Input is a Member 1 scene.json vector blueprint file.")
        return usable_path, warnings

    if ext == ".pdf":
        try:
            doc = pymupdf.open(str(input_path))
            if len(doc) == 0:
                raise ValueError(f"PDF document is empty: {input_path}")
            page = doc[0]
            # 200 DPI (default resolution is 72 DPI -> matrix zoom = 200/72 ≈ 2.777)
            zoom = 200 / 72
            mat = pymupdf.Matrix(zoom, zoom)
            pix = page.get_pixmap(matrix=mat)

            raster_path = input_path.parent / f"{input_path.stem}_processed.png"
            pix.save(str(raster_path))
            usable_path = raster_path
            warnings.append(f"Rasterized PDF page 1 to {raster_path.name} at 200 DPI")
        except Exception as e:
            raise ValueError(f"Failed to rasterize PDF file '{input_path}': {e}")

    # Inspect image resolution
    try:
        with Image.open(usable_path) as img:
            w, h = img.size
            shorter_side = min(w, h)
            if shorter_side < 400:
                warnings.append(
                    f"Low image resolution ({w}x{h} px). Shorter side is < 400px."
                )
    except Exception as e:
        raise ValueError(f"Failed to open image file '{usable_path}': {e}")

    return usable_path, warnings


def validate_scene(
    scene_data: Dict[str, Any] | Scene
) -> Tuple[bool, List[str], List[str], Dict[str, int]]:
    """
    Validate scene geometry and return (ok, errors, warnings, counters).
    """
    if isinstance(scene_data, Scene):
        scene_dict = scene_data.to_dict()
    else:
        scene_dict = scene_data

    errors: List[str] = []
    warnings: List[str] = []
    counters: Dict[str, int] = {
        "invalid_walls": 0,
        "disconnected_walls": 0,
        "doors_without_wall": 0,
        "windows_without_wall": 0,
        "self_intersecting_rooms": 0,
    }

    walls = scene_dict.get("walls", [])
    doors = scene_dict.get("doors", [])
    windows = scene_dict.get("windows", [])
    rooms = scene_dict.get("rooms", [])

    if not walls:
        errors.append("Scene contains no walls.")

    wall_map = {}
    wall_endpoints = []
    wall_lines = []

    # Validate Walls
    for wall in walls:
        wall_id = wall.get("id")
        start = wall.get("start")
        end = wall.get("end")
        thickness = wall.get("thickness", 0.0)
        height = wall.get("height", 0.0)

        is_valid = True
        if not wall_id or not isinstance(wall_id, str):
            errors.append(f"Wall missing valid id: {wall}")
            is_valid = False

        if not start or not end or len(start) != 2 or len(end) != 2:
            errors.append(f"Wall {wall_id} has invalid start/end coordinates: {start}, {end}")
            is_valid = False
        elif start[0] == end[0] and start[1] == end[1]:
            errors.append(f"Wall {wall_id} start and end points are identical: {start}")
            is_valid = False

        if thickness <= 0:
            errors.append(f"Wall {wall_id} thickness must be > 0 (got {thickness})")
            is_valid = False
        if height <= 0:
            errors.append(f"Wall {wall_id} height must be > 0 (got {height})")
            is_valid = False

        if is_valid:
            wall_map[wall_id] = wall
            p1 = (float(start[0]), float(start[1]))
            p2 = (float(end[0]), float(end[1]))
            wall_endpoints.append((wall_id, p1))
            wall_endpoints.append((wall_id, p2))
            wall_lines.append((wall_id, LineString([p1, p2]), thickness))
        else:
            counters["invalid_walls"] += 1

    # Disconnected wall check: each endpoint should be within tol = 2 * thickness of another wall
    for wall_id, line, thickness in wall_lines:
        tol = DISCONNECTED_WALL_TOL_FACTOR * thickness
        p1, p2 = Point(line.coords[0]), Point(line.coords[1])

        # Check p1 and p2 connectivity to other walls
        p1_connected = False
        p2_connected = False

        for other_id, other_line, _ in wall_lines:
            if other_id == wall_id:
                continue
            if other_line.distance(p1) <= tol:
                p1_connected = True
            if other_line.distance(p2) <= tol:
                p2_connected = True

        if not p1_connected or not p2_connected:
            counters["disconnected_walls"] += 1
            warnings.append(f"Wall {wall_id} has a disconnected endpoint (tolerance {tol:.2f}m)")

    # Validate Doors
    for door in doors:
        door_id = door.get("id")
        wall_id = door.get("wall_id")
        pos = door.get("position", -1.0)
        width = door.get("width", 0.0)
        height = door.get("height", 0.0)

        if wall_id not in wall_map:
            errors.append(f"Door {door_id} references missing wall_id '{wall_id}'")
            counters["doors_without_wall"] += 1
        else:
            wall = wall_map[wall_id]
            p1, p2 = wall["start"], wall["end"]
            wall_len = math.hypot(p2[0] - p1[0], p2[1] - p1[1])
            if width > wall_len + 1e-3:
                warnings.append(f"Door {door_id} width ({width:.2f}) exceeds wall length ({wall_len:.2f})")

        if not (0.0 <= pos <= 1.0):
            errors.append(f"Door {door_id} position {pos} out of range [0.0, 1.0]")
        if width <= 0:
            errors.append(f"Door {door_id} width must be > 0")
        if height <= 0:
            errors.append(f"Door {door_id} height must be > 0")

    # Validate Windows
    for window in windows:
        win_id = window.get("id")
        wall_id = window.get("wall_id")
        pos = window.get("position", -1.0)
        width = window.get("width", 0.0)
        sill = window.get("sill_height", -1.0)
        height = window.get("height", 0.0)

        if wall_id not in wall_map:
            errors.append(f"Window {win_id} references missing wall_id '{wall_id}'")
            counters["windows_without_wall"] += 1
        else:
            wall = wall_map[wall_id]
            wall_h = wall.get("height", 3.0)
            if sill + height > wall_h + 1e-3:
                warnings.append(
                    f"Window {win_id} top height ({sill + height:.2f}) exceeds wall height ({wall_h:.2f})"
                )

        if not (0.0 <= pos <= 1.0):
            errors.append(f"Window {win_id} position {pos} out of range [0.0, 1.0]")
        if width <= 0:
            errors.append(f"Window {win_id} width must be > 0")
        if sill < 0:
            errors.append(f"Window {win_id} sill_height must be >= 0")
        if height <= 0:
            errors.append(f"Window {win_id} height must be > 0")

    # Validate Rooms
    for room in rooms:
        room_id = room.get("id")
        poly_pts = room.get("polygon", [])
        if len(poly_pts) < 3:
            errors.append(f"Room {room_id} polygon has fewer than 3 vertices")
            continue

        try:
            polygon = Polygon(poly_pts)
            if not polygon.is_valid:
                counters["self_intersecting_rooms"] += 1
                warnings.append(f"Room {room_id} has a self-intersecting / invalid polygon")
            elif polygon.area <= 0:
                errors.append(f"Room {room_id} polygon area is 0")
        except Exception as e:
            counters["self_intersecting_rooms"] += 1
            errors.append(f"Room {room_id} polygon creation error: {e}")

    ok = len(errors) == 0
    return ok, errors, warnings, counters
