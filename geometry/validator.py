"""
Phase 1: Geometry Validator Module for Member 2.

Performs comprehensive validation of raw scene.json inputs from Member 1:
structural integrity, coordinate validity, topological anomalies, and relational sanity.
"""

from __future__ import annotations

import math
from typing import Dict, Any, List, Tuple
from shapely.geometry import Polygon

from geometry.config import (
    MIN_WALL_LENGTH,
    WALL_SNAP_TOLERANCE,
    MIN_ROOM_VERTICES,
    MIN_ROOM_AREA_PX,
)


def _is_valid_point(pt: Any) -> bool:
    if not isinstance(pt, (list, tuple)) or len(pt) < 2:
        return False
    try:
        x, y = float(pt[0]), float(pt[1])
        return math.isfinite(x) and math.isfinite(y)
    except (ValueError, TypeError):
        return False


def validate_scene(scene: Dict[str, Any]) -> Dict[str, Any]:
    """
    Validates raw scene.json against structural, geometric, and relational rules.
    Returns a structured validation report without modifying or discarding any geometry.
    """
    issues: List[Dict[str, Any]] = []

    def add_issue(issue_type: str, element_id: str, severity: str, message: str, element_type: str = "general"):
        issues.append({
            "type": issue_type,
            "element_type": element_type,
            "element_id": element_id,
            "severity": severity,
            "message": message
        })

    if not isinstance(scene, dict):
        return {
            "valid": False,
            "issues": [{
                "type": "invalid_schema",
                "element_type": "scene",
                "element_id": "root",
                "severity": "error",
                "message": "Scene data must be a JSON object"
            }],
            "stats": {}
        }

    is_meters = str(scene.get("units", "pixels")).lower() in ["meters", "meter", "m"]
    min_wall_len = 0.3 if is_meters else MIN_WALL_LENGTH
    min_room_area = 1.0 if is_meters else MIN_ROOM_AREA_PX
    snap_tol = 0.3 if is_meters else WALL_SNAP_TOLERANCE
    unit_str = "m" if is_meters else "px"

    raw_walls = scene.get("walls", [])
    raw_doors = scene.get("doors", [])
    raw_windows = scene.get("windows", [])
    raw_rooms = scene.get("rooms", [])

    # ---------------------------------------------------------
    # 1. Wall Validation
    # ---------------------------------------------------------
    valid_walls_map: Dict[str, Dict[str, Any]] = {}
    wall_endpoints: List[Tuple[str, str, Tuple[float, float]]] = []

    for idx, w in enumerate(raw_walls):
        w_id = str(w.get("id", f"wall_{idx+1}")) if isinstance(w, dict) else f"wall_{idx+1}"

        if not isinstance(w, dict):
            add_issue("invalid_wall_entry", w_id, "error", f"Wall at index {idx} is not an object", "wall")
            continue

        # Check required fields
        for field in ["id", "start", "end", "thickness"]:
            if field not in w:
                add_issue("missing_wall_field", w_id, "error", f"Wall '{w_id}' is missing required field '{field}'", "wall")

        # Check coordinates
        start_valid = _is_valid_point(w.get("start"))
        end_valid = _is_valid_point(w.get("end"))

        if not start_valid or not end_valid:
            add_issue("invalid_coordinates", w_id, "error", f"Wall '{w_id}' has invalid or non-numeric start/end coordinates", "wall")
            continue

        p_start = (float(w["start"][0]), float(w["start"][1]))
        p_end = (float(w["end"][0]), float(w["end"][1]))

        # Check thickness
        thickness = w.get("thickness")
        try:
            th_val = float(thickness)
            if not math.isfinite(th_val) or th_val <= 0.0:
                add_issue("invalid_thickness", w_id, "error", f"Wall '{w_id}' thickness ({thickness}) must be a positive finite number", "wall")
        except (ValueError, TypeError):
            add_issue("invalid_thickness", w_id, "error", f"Wall '{w_id}' thickness ({thickness}) is not a valid number", "wall")

        # Check length & zero-length
        length = math.hypot(p_end[0] - p_start[0], p_end[1] - p_start[1])
        if length < 1e-4:
            add_issue("zero_length_wall", w_id, "error", f"Wall '{w_id}' has zero or near-zero length ({length:.4f})", "wall")
        elif length < min_wall_len:
            add_issue("short_wall", w_id, "warning", f"Wall '{w_id}' is unusually short (length {length:.2f}{unit_str} < {min_wall_len}{unit_str})", "wall")

        # Check duplicate wall IDs
        if w_id in valid_walls_map:
            add_issue("duplicate_wall_id", w_id, "error", f"Duplicate wall ID '{w_id}' detected", "wall")

        valid_walls_map[w_id] = {
            "id": w_id,
            "start": p_start,
            "end": p_end,
            "length": length,
            "thickness": float(thickness) if isinstance(thickness, (int, float)) else 10.0,
            "raw": w
        }
        wall_endpoints.append((w_id, "start", p_start))
        wall_endpoints.append((w_id, "end", p_end))

    # Detect duplicate or nearly duplicate walls
    wall_ids = list(valid_walls_map.keys())
    for i in range(len(wall_ids)):
        for j in range(i + 1, len(wall_ids)):
            w1 = valid_walls_map[wall_ids[i]]
            w2 = valid_walls_map[wall_ids[j]]
            d_direct = math.hypot(w1["start"][0] - w2["start"][0], w1["start"][1] - w2["start"][1]) + \
                       math.hypot(w1["end"][0] - w2["end"][0], w1["end"][1] - w2["end"][1])
            d_rev = math.hypot(w1["start"][0] - w2["end"][0], w1["start"][1] - w2["end"][1]) + \
                    math.hypot(w1["end"][0] - w2["start"][0], w1["end"][1] - w2["start"][1])
            dup_thresh = 0.05 if is_meters else 2.0
            if min(d_direct, d_rev) < dup_thresh:
                add_issue("duplicate_wall_geometry", w1["id"], "warning",
                          f"Wall '{w1['id']}' and '{w2['id']}' are nearly identical duplicate segments", "wall")

    # Detect disconnected / isolated walls
    for w_id, w_info in valid_walls_map.items():
        connected_start = False
        connected_end = False
        for other_id, pt_type, pt in wall_endpoints:
            if other_id == w_id:
                continue
            if math.hypot(w_info["start"][0] - pt[0], w_info["start"][1] - pt[1]) <= snap_tol:
                connected_start = True
            if math.hypot(w_info["end"][0] - pt[0], w_info["end"][1] - pt[1]) <= snap_tol:
                connected_end = True
        if not connected_start and not connected_end:
            add_issue("disconnected_wall", w_id, "warning",
                      f"Wall '{w_id}' is isolated and disconnected from all other walls", "wall")

    # ---------------------------------------------------------
    # 2. Door Validation
    # ---------------------------------------------------------
    for idx, d in enumerate(raw_doors):
        d_id = str(d.get("id", f"door_{idx+1}")) if isinstance(d, dict) else f"door_{idx+1}"

        if not isinstance(d, dict):
            add_issue("invalid_door_entry", d_id, "error", f"Door at index {idx} is not an object", "door")
            continue

        w_ref = d.get("wall_id")
        if not w_ref or w_ref not in valid_walls_map:
            add_issue("missing_wall_reference", d_id, "error",
                      f"Door '{d_id}' references non-existent wall '{w_ref}'", "door")
            continue

        wall = valid_walls_map[w_ref]

        # Width check
        width = d.get("width")
        try:
            w_val = float(width)
            if not math.isfinite(w_val) or w_val <= 0.0:
                add_issue("invalid_door_width", d_id, "error",
                          f"Door '{d_id}' width ({width}) must be a positive number", "door")
            elif w_val > wall["length"]:
                add_issue("door_exceeds_wall_length", d_id, "warning",
                          f"Door '{d_id}' width ({w_val:.2f}{unit_str}) exceeds referenced wall '{w_ref}' length ({wall['length']:.2f}{unit_str})", "door")
        except (ValueError, TypeError):
            add_issue("invalid_door_width", d_id, "error", f"Door '{d_id}' width ({width}) is not numeric", "door")

        # Position check (0.0 <= position <= 1.0)
        pos = d.get("position")
        try:
            pos_val = float(pos)
            if not math.isfinite(pos_val) or pos_val < 0.0 or pos_val > 1.0:
                add_issue("invalid_door_position", d_id, "error",
                          f"Door '{d_id}' position ({pos}) must be between 0.0 and 1.0 along wall", "door")
            elif pos_val in (0.0, 1.0):
                add_issue("boundary_door_position", d_id, "warning",
                          f"Door '{d_id}' is positioned at the extreme wall boundary (position={pos_val})", "door")
        except (ValueError, TypeError):
            add_issue("invalid_door_position", d_id, "error", f"Door '{d_id}' position ({pos}) is not numeric", "door")

    # ---------------------------------------------------------
    # 3. Window Validation
    # ---------------------------------------------------------
    for idx, win in enumerate(raw_windows):
        win_id = str(win.get("id", f"win_{idx+1}")) if isinstance(win, dict) else f"win_{idx+1}"

        if not isinstance(win, dict):
            add_issue("invalid_window_entry", win_id, "error", f"Window at index {idx} is not an object", "window")
            continue

        w_ref = win.get("wall_id")
        if not w_ref or w_ref not in valid_walls_map:
            add_issue("missing_wall_reference", win_id, "error",
                      f"Window '{win_id}' references non-existent wall '{w_ref}'", "window")
            continue

        wall = valid_walls_map[w_ref]

        # Width check
        width = win.get("width")
        try:
            w_val = float(width)
            if not math.isfinite(w_val) or w_val <= 0.0:
                add_issue("invalid_window_width", win_id, "error",
                          f"Window '{win_id}' width ({width}) must be a positive number", "window")
            elif w_val > wall["length"]:
                add_issue("window_exceeds_wall_length", win_id, "warning",
                          f"Window '{win_id}' width ({w_val:.2f}{unit_str}) exceeds referenced wall '{w_ref}' length ({wall['length']:.2f}{unit_str})", "window")
        except (ValueError, TypeError):
            add_issue("invalid_window_width", win_id, "error", f"Window '{win_id}' width ({width}) is not numeric", "window")

        # Position check
        pos = win.get("position")
        try:
            pos_val = float(pos)
            if not math.isfinite(pos_val) or pos_val < 0.0 or pos_val > 1.0:
                add_issue("invalid_window_position", win_id, "error",
                          f"Window '{win_id}' position ({pos}) must be between 0.0 and 1.0 along wall", "window")
            elif pos_val in (0.0, 1.0):
                add_issue("boundary_window_position", win_id, "warning",
                          f"Window '{win_id}' is positioned at the extreme wall boundary (position={pos_val})", "window")
        except (ValueError, TypeError):
            add_issue("invalid_window_position", win_id, "error", f"Window '{win_id}' position ({pos}) is not numeric", "window")

    # ---------------------------------------------------------
    # 4. Room Validation
    # ---------------------------------------------------------
    for idx, r in enumerate(raw_rooms):
        r_id = str(r.get("id", f"room_{idx+1}")) if isinstance(r, dict) else f"room_{idx+1}"

        if not isinstance(r, dict):
            add_issue("invalid_room_entry", r_id, "error", f"Room at index {idx} is not an object", "room")
            continue

        poly_pts = r.get("polygon", [])
        if not isinstance(poly_pts, list) or len(poly_pts) < MIN_ROOM_VERTICES:
            add_issue("insufficient_polygon_vertices", r_id, "error",
                      f"Room '{r_id}' polygon has fewer than {MIN_ROOM_VERTICES} vertices ({len(poly_pts) if isinstance(poly_pts, list) else 0})", "room")
            continue

        valid_pts = []
        has_invalid_coord = False
        for pt_idx, pt in enumerate(poly_pts):
            if not _is_valid_point(pt):
                has_invalid_coord = True
                add_issue("invalid_room_coordinate", r_id, "error",
                          f"Room '{r_id}' vertex {pt_idx} ({pt}) has invalid or non-numeric coordinates", "room")
            else:
                valid_pts.append((float(pt[0]), float(pt[1])))

        if has_invalid_coord or len(valid_pts) < 3:
            continue

        # Geometric validity via Shapely
        try:
            poly = Polygon(valid_pts)
            if not poly.is_valid:
                add_issue("self_intersecting_room_polygon", r_id, "error",
                          f"Room '{r_id}' polygon is self-intersecting or topologically invalid", "room")
            elif poly.area < min_room_area:
                add_issue("degenerate_room_area", r_id, "error",
                          f"Room '{r_id}' polygon area is degenerate or near-zero ({poly.area:.2f} {unit_str}²)", "room")
        except Exception as e:
            add_issue("room_polygon_exception", r_id, "error",
                      f"Failed to construct polygon for room '{r_id}': {e}", "room")

    # Has any hard errors?
    has_errors = any(i["severity"] == "error" for i in issues)

    return {
        "valid": not has_errors,
        "issues": issues,
        "stats": {
            "wall_count": len(raw_walls),
            "door_count": len(raw_doors),
            "window_count": len(raw_windows),
            "room_count": len(raw_rooms),
            "error_count": len([i for i in issues if i["severity"] == "error"]),
            "warning_count": len([i for i in issues if i["severity"] == "warning"]),
            "short_walls": len([i for i in issues if i["type"] == "short_wall"]),
        }
    }
