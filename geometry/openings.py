"""
Phase 3: Door & Window Relationships Module for Member 2.

Validates relationships between openings (doors, windows) and their host walls.
Computes explicit 2D coordinates (center, start, end, offset) while preserving source definitions.
"""

from __future__ import annotations

import math
from typing import Dict, Any, List, Optional, Tuple


def _compute_opening_geometry(
    wall_start: Tuple[float, float],
    wall_end: Tuple[float, float],
    position: float,
    width: float
) -> Dict[str, Any]:
    """
    Computes absolute 2D center, start, and end coordinates for an opening on a wall.
    """
    x1, y1 = wall_start
    x2, y2 = wall_end
    dx = x2 - x1
    dy = y2 - y1
    wall_len = math.hypot(dx, dy)

    if wall_len < 1e-4:
        return {
            "center": [x1, y1],
            "start": [x1, y1],
            "end": [x1, y1],
            "width": width,
            "offset_from_start": 0.0
        }

    ux = dx / wall_len
    uy = dy / wall_len

    # Center of opening
    cx = x1 + position * dx
    cy = y1 + position * dy

    # Half width displacement along wall
    half_w = width / 2.0
    sx = cx - half_w * ux
    sy = cy - half_w * uy
    ex = cx + half_w * ux
    ey = cy + half_w * uy

    offset_from_start = max(0.0, position * wall_len - half_w)

    return {
        "center": [round(cx, 2), round(cy, 2)],
        "start": [round(sx, 2), round(sy, 2)],
        "end": [round(ex, 2), round(ey, 2)],
        "width": round(width, 2),
        "offset_from_start": round(offset_from_start, 2)
    }


def process_openings(
    doors_data: List[Dict[str, Any]],
    windows_data: List[Dict[str, Any]],
    walls_map: Dict[str, Dict[str, Any]]
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]], List[Dict[str, Any]]]:
    """
    Processes all doors and windows, resolving geometric positions from host walls.
    Returns (processed_doors, processed_windows, opening_issues).
    """
    processed_doors: List[Dict[str, Any]] = []
    processed_windows: List[Dict[str, Any]] = []
    issues: List[Dict[str, Any]] = []

    # 1. Doors
    for idx, d in enumerate(doors_data):
        d_id = str(d.get("id", f"door_{idx+1}"))
        w_id = str(d.get("wall_id", ""))

        if w_id not in walls_map:
            issues.append({
                "type": "unresolved_host_wall",
                "element_id": d_id,
                "element_type": "door",
                "severity": "error",
                "message": f"Door '{d_id}' references unknown wall '{w_id}'"
            })
            continue

        wall = walls_map[w_id]
        w_geom = wall["geometry"]
        p_start = tuple(w_geom["start"])
        p_end = tuple(w_geom["end"])
        pos = float(d.get("position", 0.5))
        w_val = float(d.get("width", 24.0))

        explicit_geom = _compute_opening_geometry(p_start, p_end, pos, w_val)

        processed_doors.append({
            "id": d_id,
            "wall_id": w_id,
            "source": {
                "position": pos,
                "width": w_val
            },
            "geometry": explicit_geom,
            # Top-level mirrors for convenience
            "position": pos,
            "width": w_val
        })

    # 2. Windows
    for idx, win in enumerate(windows_data):
        win_id = str(win.get("id", f"win_{idx+1}"))
        w_id = str(win.get("wall_id", ""))

        if w_id not in walls_map:
            issues.append({
                "type": "unresolved_host_wall",
                "element_id": win_id,
                "element_type": "window",
                "severity": "error",
                "message": f"Window '{win_id}' references unknown wall '{w_id}'"
            })
            continue

        wall = walls_map[w_id]
        w_geom = wall["geometry"]
        p_start = tuple(w_geom["start"])
        p_end = tuple(w_geom["end"])
        pos = float(win.get("position", 0.5))
        w_val = float(win.get("width", 24.0))

        explicit_geom = _compute_opening_geometry(p_start, p_end, pos, w_val)

        processed_windows.append({
            "id": win_id,
            "wall_id": w_id,
            "source": {
                "position": pos,
                "width": w_val
            },
            "geometry": explicit_geom,
            "position": pos,
            "width": w_val
        })

    return processed_doors, processed_windows, issues
