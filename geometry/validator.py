"""
Phase 1: Geometry Validator Module for Member 2.

Performs comprehensive validation of scene inputs (both raw and normalized):
structural integrity, coordinate validity, topological connectivity, opening bounds,
and polygon sanity. Implements 3-tier severity classification: ERROR, WARNING, INFO.
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


def _point_to_segment_dist(pt: Tuple[float, float], seg_s: Tuple[float, float], seg_e: Tuple[float, float]) -> float:
    """Returns minimum Euclidean distance from point to finite segment."""
    px, py = pt
    x1, y1 = seg_s
    x2, y2 = seg_e
    dx = x2 - x1
    dy = y2 - y1
    seg_len_sq = dx * dx + dy * dy
    if seg_len_sq < 1e-6:
        return math.hypot(px - x1, py - y1)
    t = max(0.0, min(1.0, ((px - x1) * dx + (py - y1) * dy) / seg_len_sq))
    proj_x = x1 + t * dx
    proj_y = y1 + t * dy
    return math.hypot(px - proj_x, py - proj_y)


def validate_scene(scene: Dict[str, Any]) -> Dict[str, Any]:
    """
    Validates scene geometry against structural, topological, and opening rules.
    Returns structured report with tiered severity: ERROR, WARNING, INFO.
    """
    issues: List[Dict[str, Any]] = []

    def add_issue(issue_type: str, element_id: str, severity: str, message: str, element_type: str = "general"):
        issues.append({
            "type": issue_type,
            "element_type": element_type,
            "element_id": element_id,
            "severity": severity.upper(),
            "message": message
        })

    if not isinstance(scene, dict):
        err = {
            "type": "invalid_schema",
            "element_type": "scene",
            "element_id": "root",
            "severity": "ERROR",
            "message": "Scene data must be a JSON object"
        }
        return {
            "status": "FAIL",
            "valid": False,
            "errors": [err],
            "warnings": [],
            "info": [],
            "issues": [err],
            "summary": {"status": "FAIL", "error_count": 1, "warning_count": 0, "info_count": 0},
            "stats": {"error_count": 1, "warning_count": 0}
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

    for idx, w in enumerate(raw_walls):
        w_id = str(w.get("id", f"wall_{idx+1}")) if isinstance(w, dict) else f"wall_{idx+1}"

        if not isinstance(w, dict):
            add_issue("invalid_wall_entry", w_id, "ERROR", f"Wall at index {idx} is not an object", "wall")
            continue

        # Check required fields
        for field in ["id", "start", "end", "thickness"]:
            if field not in w and (field not in w.get("geometry", {})):
                add_issue("missing_wall_field", w_id, "ERROR", f"Wall '{w_id}' is missing required field '{field}'", "wall")

        # Resolve coordinates (from top-level or nested geometry)
        w_geom = w.get("geometry", {})
        start_pt = w.get("start", w_geom.get("start"))
        end_pt = w.get("end", w_geom.get("end"))

        start_valid = _is_valid_point(start_pt)
        end_valid = _is_valid_point(end_pt)

        if not start_valid or not end_valid:
            add_issue("invalid_coordinates", w_id, "ERROR", f"Wall '{w_id}' has invalid or non-numeric start/end coordinates", "wall")
            continue

        p_start = (float(start_pt[0]), float(start_pt[1]))
        p_end = (float(end_pt[0]), float(end_pt[1]))

        # Check thickness
        thickness = w.get("thickness", w_geom.get("thickness"))
        try:
            th_val = float(thickness)
            if not math.isfinite(th_val) or th_val <= 0.0:
                add_issue("invalid_thickness", w_id, "ERROR", f"Wall '{w_id}' thickness ({thickness}) must be a positive finite number", "wall")
            else:
                max_th = 1.0 if is_meters else 100.0
                min_th = 0.05 if is_meters else 2.0
                if th_val < min_th or th_val > max_th:
                    add_issue("unusual_wall_thickness", w_id, "WARNING", f"Wall '{w_id}' thickness ({th_val:.2f}{unit_str}) is unusual", "wall")
        except (ValueError, TypeError):
            add_issue("invalid_thickness", w_id, "ERROR", f"Wall '{w_id}' thickness ({thickness}) is not a valid number", "wall")

        # Check length & zero-length
        length = math.hypot(p_end[0] - p_start[0], p_end[1] - p_start[1])
        if length < 1e-4:
            add_issue("zero_length_wall", w_id, "ERROR", f"Wall '{w_id}' has zero or near-zero length ({length:.4f})", "wall")
        elif length < min_wall_len:
            add_issue("short_wall", w_id, "WARNING", f"Wall '{w_id}' is unusually short (length {length:.2f}{unit_str} < {min_wall_len}{unit_str})", "wall")

        # Check duplicate wall IDs
        if w_id in valid_walls_map:
            add_issue("duplicate_wall_id", w_id, "ERROR", f"Duplicate wall ID '{w_id}' detected", "wall")

        valid_walls_map[w_id] = {
            "id": w_id,
            "start": p_start,
            "end": p_end,
            "length": length,
            "thickness": float(thickness) if isinstance(thickness, (int, float)) else 10.0,
            "raw": w
        }

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
                add_issue("duplicate_wall_geometry", w1["id"], "WARNING",
                          f"Wall '{w1['id']}' and '{w2['id']}' are nearly identical duplicate segments", "wall")

    # Detect disconnected / isolated walls (accounting for endpoint-to-endpoint and T-junctions)
    for i, w1_id in enumerate(wall_ids):
        w1 = valid_walls_map[w1_id]
        has_connection = False

        for j, w2_id in enumerate(wall_ids):
            if i == j:
                continue
            w2 = valid_walls_map[w2_id]
            # 1. Endpoint-to-endpoint distance
            d_ss = math.hypot(w1["start"][0] - w2["start"][0], w1["start"][1] - w2["start"][1])
            d_se = math.hypot(w1["start"][0] - w2["end"][0], w1["start"][1] - w2["end"][1])
            d_es = math.hypot(w1["end"][0] - w2["start"][0], w1["end"][1] - w2["start"][1])
            d_ee = math.hypot(w1["end"][0] - w2["end"][0], w1["end"][1] - w2["end"][1])
            if min(d_ss, d_se, d_es, d_ee) <= snap_tol:
                has_connection = True
                break

            # 2. T-junctions: w1 endpoint touching w2 body
            d_s_body = _point_to_segment_dist(w1["start"], w2["start"], w2["end"])
            d_e_body = _point_to_segment_dist(w1["end"], w2["start"], w2["end"])
            if min(d_s_body, d_e_body) <= snap_tol:
                has_connection = True
                break

            # 3. T-junctions: w2 endpoint touching w1 body
            d_w2s_body = _point_to_segment_dist(w2["start"], w1["start"], w1["end"])
            d_w2e_body = _point_to_segment_dist(w2["end"], w1["start"], w1["end"])
            if min(d_w2s_body, d_w2e_body) <= snap_tol:
                has_connection = True
                break

        if not has_connection and len(wall_ids) > 1:
            add_issue("disconnected_wall", w1_id, "WARNING",
                      f"Wall '{w1_id}' is isolated and disconnected from all other walls", "wall")

    # ---------------------------------------------------------
    # 2. Door Validation
    # ---------------------------------------------------------
    for idx, d in enumerate(raw_doors):
        d_id = str(d.get("id", f"door_{idx+1}")) if isinstance(d, dict) else f"door_{idx+1}"

        if not isinstance(d, dict):
            add_issue("invalid_door_entry", d_id, "ERROR", f"Door at index {idx} is not an object", "door")
            continue

        w_ref = d.get("wall_id")
        if not w_ref or w_ref not in valid_walls_map:
            add_issue("missing_wall_reference", d_id, "ERROR",
                      f"Door '{d_id}' references non-existent wall '{w_ref}'", "door")
            continue

        wall = valid_walls_map[w_ref]
        wall_len = wall["length"]

        # Width check
        width = d.get("width")
        try:
            w_val = float(width)
            if not math.isfinite(w_val) or w_val <= 0.0:
                add_issue("invalid_door_width", d_id, "ERROR",
                          f"Door '{d_id}' width ({width}) must be a positive number", "door")
                continue
            elif w_val > wall_len + 0.01:
                add_issue("door_exceeds_wall_length", d_id, "WARNING",
                          f"Door '{d_id}' width ({w_val:.2f}{unit_str}) exceeds referenced wall '{w_ref}' length ({wall_len:.2f}{unit_str})", "door")
        except (ValueError, TypeError):
            add_issue("invalid_door_width", d_id, "ERROR", f"Door '{d_id}' width ({width}) is not numeric", "door")
            continue

        # Position / Offset check
        offset = None
        if "offset" in d:
            try:
                offset = float(d["offset"])
            except (ValueError, TypeError):
                pass

        if offset is None and "position" in d:
            pos = d.get("position")
            try:
                pos_val = float(pos)
                if not math.isfinite(pos_val) or pos_val < 0.0 or pos_val > 1.0:
                    add_issue("invalid_door_position", d_id, "ERROR",
                              f"Door '{d_id}' position ({pos}) must be between 0.0 and 1.0 along wall", "door")
                else:
                    offset = pos_val * wall_len
            except (ValueError, TypeError):
                add_issue("invalid_door_position", d_id, "ERROR", f"Door '{d_id}' position ({pos}) is not numeric", "door")

        if offset is not None:
            half_w = w_val / 2.0
            s_open = offset - half_w
            e_open = offset + half_w

            if s_open < -0.05 or e_open > wall_len + 0.05:
                add_issue("door_outside_wall", d_id, "ERROR",
                          f"Door '{d_id}' opening [{s_open:.2f}, {e_open:.2f}] extends outside wall '{w_ref}' length ({wall_len:.2f})", "door")
            elif s_open <= 0.01 or e_open >= wall_len - 0.01:
                add_issue("boundary_door_position", d_id, "WARNING",
                          f"Door '{d_id}' is positioned at the extreme wall boundary", "door")

    # ---------------------------------------------------------
    # 3. Window Validation
    # ---------------------------------------------------------
    for idx, win in enumerate(raw_windows):
        win_id = str(win.get("id", f"win_{idx+1}")) if isinstance(win, dict) else f"win_{idx+1}"

        if not isinstance(win, dict):
            add_issue("invalid_window_entry", win_id, "ERROR", f"Window at index {idx} is not an object", "window")
            continue

        w_ref = win.get("wall_id")
        if not w_ref or w_ref not in valid_walls_map:
            add_issue("missing_wall_reference", win_id, "ERROR",
                      f"Window '{win_id}' references non-existent wall '{w_ref}'", "window")
            continue

        wall = valid_walls_map[w_ref]
        wall_len = wall["length"]

        # Width check
        width = win.get("width")
        try:
            w_val = float(width)
            if not math.isfinite(w_val) or w_val <= 0.0:
                add_issue("invalid_window_width", win_id, "ERROR",
                          f"Window '{win_id}' width ({width}) must be a positive number", "window")
                continue
            elif w_val > wall_len + 0.01:
                add_issue("window_exceeds_wall_length", win_id, "WARNING",
                          f"Window '{win_id}' width ({w_val:.2f}{unit_str}) exceeds referenced wall '{w_ref}' length ({wall_len:.2f}{unit_str})", "window")
        except (ValueError, TypeError):
            add_issue("invalid_window_width", win_id, "ERROR", f"Window '{win_id}' width ({width}) is not numeric", "window")
            continue

        # Position / Offset check
        offset = None
        if "offset" in win:
            try:
                offset = float(win["offset"])
            except (ValueError, TypeError):
                pass

        if offset is None and "position" in win:
            pos = win.get("position")
            try:
                pos_val = float(pos)
                if not math.isfinite(pos_val) or pos_val < 0.0 or pos_val > 1.0:
                    add_issue("invalid_window_position", win_id, "ERROR",
                              f"Window '{win_id}' position ({pos}) must be between 0.0 and 1.0 along wall", "window")
                else:
                    offset = pos_val * wall_len
            except (ValueError, TypeError):
                add_issue("invalid_window_position", win_id, "ERROR", f"Window '{win_id}' position ({pos}) is not numeric", "window")

        if offset is not None:
            half_w = w_val / 2.0
            s_open = offset - half_w
            e_open = offset + half_w

            if s_open < -0.05 or e_open > wall_len + 0.05:
                add_issue("window_outside_wall", win_id, "ERROR",
                          f"Window '{win_id}' opening [{s_open:.2f}, {e_open:.2f}] extends outside wall '{w_ref}' length ({wall_len:.2f})", "window")
            elif s_open <= 0.01 or e_open >= wall_len - 0.01:
                add_issue("boundary_window_position", win_id, "WARNING",
                          f"Window '{win_id}' is positioned at the extreme wall boundary", "window")

    # ---------------------------------------------------------
    # 4. Room Validation
    # ---------------------------------------------------------
    for idx, r in enumerate(raw_rooms):
        r_id = str(r.get("id", f"room_{idx+1}")) if isinstance(r, dict) else f"room_{idx+1}"

        if not isinstance(r, dict):
            add_issue("invalid_room_entry", r_id, "ERROR", f"Room at index {idx} is not an object", "room")
            continue

        poly_pts = r.get("polygon", r.get("geometry", {}).get("polygon", []))
        if not isinstance(poly_pts, list) or len(poly_pts) < MIN_ROOM_VERTICES:
            add_issue("insufficient_polygon_vertices", r_id, "ERROR",
                      f"Room '{r_id}' polygon has fewer than {MIN_ROOM_VERTICES} vertices ({len(poly_pts) if isinstance(poly_pts, list) else 0})", "room")
            continue

        valid_pts = []
        has_invalid_coord = False
        for pt_idx, pt in enumerate(poly_pts):
            if not _is_valid_point(pt):
                has_invalid_coord = True
                add_issue("invalid_room_coordinate", r_id, "ERROR",
                          f"Room '{r_id}' vertex {pt_idx} ({pt}) has invalid or non-numeric coordinates", "room")
            else:
                valid_pts.append((float(pt[0]), float(pt[1])))

        if has_invalid_coord or len(valid_pts) < 3:
            continue

        # Geometric validity via Shapely
        try:
            poly = Polygon(valid_pts)
            if not poly.is_valid:
                add_issue("self_intersecting_room_polygon", r_id, "ERROR",
                          f"Room '{r_id}' polygon is self-intersecting or topologically invalid", "room")
            elif poly.area < min_room_area:
                add_issue("degenerate_room_area", r_id, "ERROR",
                          f"Room '{r_id}' polygon area is degenerate or near-zero ({poly.area:.2f} {unit_str}²)", "room")
        except Exception as e:
            add_issue("room_polygon_exception", r_id, "ERROR",
                      f"Failed to construct polygon for room '{r_id}': {e}", "room")

    # Categorize issues by severity
    errors = [i for i in issues if i["severity"] == "ERROR"]
    warnings = [i for i in issues if i["severity"] == "WARNING"]
    info = [i for i in issues if i["severity"] == "INFO"]
    has_errors = len(errors) > 0
    status_str = "FAIL" if has_errors else "PASS"

    return {
        "status": status_str,
        "valid": not has_errors,
        "errors": errors,
        "warnings": warnings,
        "info": info,
        "issues": issues,
        "summary": {
            "status": status_str,
            "wall_count": len(raw_walls),
            "door_count": len(raw_doors),
            "window_count": len(raw_windows),
            "room_count": len(raw_rooms),
            "error_count": len(errors),
            "warning_count": len(warnings),
            "info_count": len(info),
            "short_walls": len([i for i in issues if i["type"] == "short_wall"]),
        },
        "stats": {
            "wall_count": len(raw_walls),
            "door_count": len(raw_doors),
            "window_count": len(raw_windows),
            "room_count": len(raw_rooms),
            "error_count": len(errors),
            "warning_count": len(warnings),
            "info_count": len(info),
            "short_walls": len([i for i in issues if i["type"] == "short_wall"]),
        }
    }
