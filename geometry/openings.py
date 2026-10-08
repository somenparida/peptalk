"""
Phase 3: Door & Window Relationships Module for Member 2.

Validates relationships between openings (doors, windows) and their host walls.
Computes canonical offset (distance from wall start to center), opening intervals,
absolute coordinates, and handles wall re-association with complete provenance.
"""

from __future__ import annotations

import math
from typing import Dict, Any, List, Optional, Tuple


def _compute_canonical_opening(
    host_wall: Dict[str, Any],
    orig_center: Tuple[float, float],
    width: float,
    height: float,
    opening_type: str = "door",
    sill_height: float = 0.0
) -> Dict[str, Any]:
    """
    Computes canonical opening representation on a host wall.
    offset = distance from wall start to opening center.
    """
    p_start = tuple(float(c) for c in host_wall["geometry"]["start"])
    p_end = tuple(float(c) for c in host_wall["geometry"]["end"])

    dx = p_end[0] - p_start[0]
    dy = p_end[1] - p_start[1]
    wall_len = math.hypot(dx, dy)

    if wall_len < 1e-4:
        return {
            "offset": 0.0,
            "width": width,
            "opening_start": 0.0,
            "opening_end": width,
            "fits_within_wall": False,
            "center": list(p_start),
            "start": list(p_start),
            "end": list(p_start),
            "position": 0.0
        }

    ux = dx / wall_len
    uy = dy / wall_len

    # Project original center point onto host wall vector
    vx = orig_center[0] - p_start[0]
    vy = orig_center[1] - p_start[1]
    raw_offset = vx * ux + vy * uy

    # If opening extends slightly outside wall boundary, adjust if it's within tolerance
    half_w = width / 2.0
    s_open = raw_offset - half_w
    e_open = raw_offset + half_w

    if s_open < 0.0 and abs(s_open) <= half_w + 1.0:
        raw_offset = half_w
    elif e_open > wall_len and (e_open - wall_len) <= half_w + 1.0:
        raw_offset = wall_len - half_w

    offset = round(max(0.0, min(wall_len, raw_offset)), 2)
    s_open = round(offset - half_w, 2)
    e_open = round(offset + half_w, 2)
    fits = (s_open >= -0.01) and (e_open <= wall_len + 0.01)

    # Compute absolute 2D start, center, and end points
    cx = round(p_start[0] + offset * ux, 2)
    cy = round(p_start[1] + offset * uy, 2)
    sx = round(p_start[0] + s_open * ux, 2)
    sy = round(p_start[1] + s_open * uy, 2)
    ex = round(p_start[0] + e_open * ux, 2)
    ey = round(p_start[1] + e_open * uy, 2)

    position = round(offset / wall_len, 4) if wall_len > 0 else 0.0

    result = {
        "offset": offset,
        "width": round(width, 2),
        "height": round(height, 2),
        "opening_start": s_open,
        "opening_end": e_open,
        "fits_within_wall": fits,
        "center": [cx, cy],
        "start": [sx, sy],
        "end": [ex, ey],
        "position": position,  # Backward compatibility
    }

    if opening_type == "window":
        result["sill_height"] = round(sill_height, 2)

    return result


def process_openings(
    doors_data: List[Dict[str, Any]],
    windows_data: List[Dict[str, Any]],
    walls_map: Dict[str, Dict[str, Any]],
    wall_reassignments: Optional[Dict[str, str]] = None,
    raw_walls_map: Optional[Dict[str, Dict[str, Any]]] = None
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]], List[Dict[str, Any]]]:
    """
    Validates and canonicalizes doors and windows.
    Resolves host wall re-associations and computes explicit opening intervals.
    """
    reassign = wall_reassignments or {}
    raw_map = raw_walls_map or walls_map

    processed_doors: List[Dict[str, Any]] = []
    processed_windows: List[Dict[str, Any]] = []
    issues: List[Dict[str, Any]] = []

    # 1. Process Doors
    for idx, d in enumerate(doors_data):
        d_id = str(d.get("id", f"door_{idx+1}"))
        orig_w_id = str(d.get("wall_id", ""))
        target_w_id = reassign.get(orig_w_id, orig_w_id)

        if target_w_id not in walls_map:
            issues.append({
                "type": "missing_wall_reference",
                "severity": "ERROR",
                "element_id": d_id,
                "element_type": "door",
                "message": f"Door '{d_id}' references non-existent wall '{target_w_id}'"
            })
            continue

        host_wall = walls_map[target_w_id]
        orig_wall = raw_map.get(orig_w_id, host_wall)

        # Compute original world center
        pos = float(d.get("position", d.get("offset", 0.5)))
        w_val = float(d.get("width", 24.0))
        h_val = float(d.get("height", 2.1))

        # Check if position is already absolute offset or normalized [0, 1]
        orig_ws = orig_wall.get("start", orig_wall.get("geometry", {}).get("start"))
        orig_we = orig_wall.get("end", orig_wall.get("geometry", {}).get("end"))
        ow_len = math.hypot(orig_we[0] - orig_ws[0], orig_we[1] - orig_ws[1])

        if "offset" in d and not ("position" in d):
            orig_cx = orig_ws[0] + (pos / ow_len) * (orig_we[0] - orig_ws[0]) if ow_len > 0 else orig_ws[0]
            orig_cy = orig_ws[1] + (pos / ow_len) * (orig_we[1] - orig_ws[1]) if ow_len > 0 else orig_ws[1]
        else:
            orig_cx = orig_ws[0] + pos * (orig_we[0] - orig_ws[0])
            orig_cy = orig_ws[1] + pos * (orig_we[1] - orig_ws[1])

        canonical = _compute_canonical_opening(
            host_wall=host_wall,
            orig_center=(orig_cx, orig_cy),
            width=w_val,
            height=h_val,
            opening_type="door"
        )

        is_reassigned = (orig_w_id != target_w_id)
        door_entry = {
            "id": d_id,
            "type": "door",
            "wall_id": target_w_id,
            "source_wall_id": orig_w_id,
            "corrected": is_reassigned,
            "correction_reason": "host_wall_reassigned_after_topology_cleanup" if is_reassigned else None,
            "source": {
                "wall_id": orig_w_id,
                "position": d.get("position"),
                "width": w_val
            },
            # Canonical representation
            "offset": canonical["offset"],
            "width": canonical["width"],
            "height": canonical["height"],
            "opening_start": canonical["opening_start"],
            "opening_end": canonical["opening_end"],
            "geometry": {
                "center": canonical["center"],
                "start": canonical["start"],
                "end": canonical["end"],
                "opening_start": canonical["opening_start"],
                "opening_end": canonical["opening_end"],
                "fits_within_wall": canonical["fits_within_wall"]
            },
            # Backward compatibility
            "position": canonical["position"]
        }
        processed_doors.append(door_entry)

        if not canonical["fits_within_wall"]:
            issues.append({
                "type": "door_outside_wall",
                "severity": "ERROR",
                "element_id": d_id,
                "element_type": "door",
                "message": f"Door '{d_id}' opening [{canonical['opening_start']}, {canonical['opening_end']}] extends outside wall '{target_w_id}' length ({host_wall['geometry']['length']})"
            })
        elif canonical["opening_start"] <= 0.01 or canonical["opening_end"] >= host_wall["geometry"]["length"] - 0.01:
            issues.append({
                "type": "boundary_door_position",
                "severity": "WARNING",
                "element_id": d_id,
                "element_type": "door",
                "message": f"Door '{d_id}' opening touches the extreme wall boundary"
            })

    # 2. Process Windows
    for idx, win in enumerate(windows_data):
        win_id = str(win.get("id", f"win_{idx+1}"))
        orig_w_id = str(win.get("wall_id", ""))
        target_w_id = reassign.get(orig_w_id, orig_w_id)

        if target_w_id not in walls_map:
            issues.append({
                "type": "missing_wall_reference",
                "severity": "ERROR",
                "element_id": win_id,
                "element_type": "window",
                "message": f"Window '{win_id}' references non-existent wall '{target_w_id}'"
            })
            continue

        host_wall = walls_map[target_w_id]
        orig_wall = raw_map.get(orig_w_id, host_wall)

        pos = float(win.get("position", win.get("offset", 0.5)))
        w_val = float(win.get("width", 24.0))
        h_val = float(win.get("height", 1.2))
        sill_val = float(win.get("sill_height", 0.9))

        orig_ws = orig_wall.get("start", orig_wall.get("geometry", {}).get("start"))
        orig_we = orig_wall.get("end", orig_wall.get("geometry", {}).get("end"))
        ow_len = math.hypot(orig_we[0] - orig_ws[0], orig_we[1] - orig_ws[1])

        if "offset" in win and not ("position" in win):
            orig_cx = orig_ws[0] + (pos / ow_len) * (orig_we[0] - orig_ws[0]) if ow_len > 0 else orig_ws[0]
            orig_cy = orig_ws[1] + (pos / ow_len) * (orig_we[1] - orig_ws[1]) if ow_len > 0 else orig_ws[1]
        else:
            orig_cx = orig_ws[0] + pos * (orig_we[0] - orig_ws[0])
            orig_cy = orig_ws[1] + pos * (orig_we[1] - orig_ws[1])

        canonical = _compute_canonical_opening(
            host_wall=host_wall,
            orig_center=(orig_cx, orig_cy),
            width=w_val,
            height=h_val,
            opening_type="window",
            sill_height=sill_val
        )

        is_reassigned = (orig_w_id != target_w_id)
        win_entry = {
            "id": win_id,
            "type": "window",
            "wall_id": target_w_id,
            "source_wall_id": orig_w_id,
            "corrected": is_reassigned,
            "correction_reason": "host_wall_reassigned_after_topology_cleanup" if is_reassigned else None,
            "source": {
                "wall_id": orig_w_id,
                "position": win.get("position"),
                "width": w_val
            },
            # Canonical representation
            "offset": canonical["offset"],
            "width": canonical["width"],
            "height": canonical["height"],
            "sill_height": canonical["sill_height"],
            "opening_start": canonical["opening_start"],
            "opening_end": canonical["opening_end"],
            "geometry": {
                "center": canonical["center"],
                "start": canonical["start"],
                "end": canonical["end"],
                "opening_start": canonical["opening_start"],
                "opening_end": canonical["opening_end"],
                "fits_within_wall": canonical["fits_within_wall"]
            },
            # Backward compatibility
            "position": canonical["position"]
        }
        processed_windows.append(win_entry)

        if not canonical["fits_within_wall"]:
            issues.append({
                "type": "window_outside_wall",
                "severity": "ERROR",
                "element_id": win_id,
                "element_type": "window",
                "message": f"Window '{win_id}' opening [{canonical['opening_start']}, {canonical['opening_end']}] extends outside wall '{target_w_id}' length ({host_wall['geometry']['length']})"
            })
        elif canonical["opening_start"] <= 0.01 or canonical["opening_end"] >= host_wall["geometry"]["length"] - 0.01:
            issues.append({
                "type": "boundary_window_position",
                "severity": "WARNING",
                "element_id": win_id,
                "element_type": "window",
                "message": f"Window '{win_id}' opening touches the extreme wall boundary"
            })

    return processed_doors, processed_windows, issues
