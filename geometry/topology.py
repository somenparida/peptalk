"""
Phase 2: Topology Cleanup Module for Member 2.

Handles endpoint snapping, T-junction detection, collinear wall fragment merging,
extraction artifact removal, and complete provenance tracking.
"""

from __future__ import annotations

import math
from typing import Dict, Any, List, Tuple, Optional
import numpy as np

from geometry.config import (
    TOPOLOGY_SNAP_TOLERANCE,
    WALL_MERGE_TOLERANCE,
    COLINEAR_ANGLE_TOLERANCE_DEG,
    CORNER_SNAP_TOLERANCE,
    MIN_WALL_LENGTH,
    MERGE_COLLINEAR_FRAGMENTS,
    REMOVE_EXTRACTION_ARTIFACTS,
)


def _distance(p1: Tuple[float, float], p2: Tuple[float, float]) -> float:
    return math.hypot(p1[0] - p2[0], p1[1] - p2[1])


def _point_to_line_dist(
    pt: Tuple[float, float],
    l_start: Tuple[float, float],
    l_end: Tuple[float, float]
) -> float:
    """Perpendicular distance from point to infinite line passing through l_start and l_end."""
    x0, y0 = pt
    x1, y1 = l_start
    x2, y2 = l_end
    num = abs((y2 - y1) * x0 - (x2 - x1) * y0 + x2 * y1 - y2 * x1)
    den = math.hypot(y2 - y1, x2 - x1)
    return num / den if den > 1e-6 else _distance(pt, l_start)


def _point_to_segment_distance(
    pt: Tuple[float, float],
    seg_start: Tuple[float, float],
    seg_end: Tuple[float, float]
) -> Tuple[float, Tuple[float, float]]:
    """Returns distance from point to segment and the projected point on the segment."""
    px, py = pt
    x1, y1 = seg_start
    x2, y2 = seg_end
    dx = x2 - x1
    dy = y2 - y1
    seg_len_sq = dx * dx + dy * dy

    if seg_len_sq < 1e-6:
        return _distance(pt, seg_start), seg_start

    t = max(0.0, min(1.0, ((px - x1) * dx + (py - y1) * dy) / seg_len_sq))
    proj_x = x1 + t * dx
    proj_y = y1 + t * dy
    dist = math.hypot(px - proj_x, py - proj_y)
    return dist, (proj_x, proj_y)


def _are_walls_collinear(
    w1: Dict[str, Any],
    w2: Dict[str, Any],
    angle_tol_deg: float = COLINEAR_ANGLE_TOLERANCE_DEG,
    dist_tol: float = WALL_MERGE_TOLERANCE
) -> bool:
    """Checks if two walls are approximately collinear."""
    p1s = tuple(w1["geometry"]["start"])
    p1e = tuple(w1["geometry"]["end"])
    p2s = tuple(w2["geometry"]["start"])
    p2e = tuple(w2["geometry"]["end"])

    dx1 = p1e[0] - p1s[0]
    dy1 = p1e[1] - p1s[1]
    dx2 = p2e[0] - p2s[0]
    dy2 = p2e[1] - p2s[1]

    len1 = math.hypot(dx1, dy1)
    len2 = math.hypot(dx2, dy2)
    if len1 < 1e-4 or len2 < 1e-4:
        return False

    ang1 = math.degrees(math.atan2(dy1, dx1)) % 180.0
    ang2 = math.degrees(math.atan2(dy2, dx2)) % 180.0
    ang_diff = abs(ang1 - ang2)
    if ang_diff > 90.0:
        ang_diff = 180.0 - ang_diff

    if ang_diff > angle_tol_deg:
        return False

    # Check lateral distance from endpoints of w2 to line of w1
    d1 = _point_to_line_dist(p2s, p1s, p1e)
    d2 = _point_to_line_dist(p2e, p1s, p1e)
    return (d1 <= dist_tol) and (d2 <= dist_tol)


def snap_endpoints(
    walls: List[Dict[str, Any]],
    tolerance: float = TOPOLOGY_SNAP_TOLERANCE
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """
    Finds clusters of wall endpoints within tolerance and snaps them to cluster centroids.
    Prevents endpoints of the SAME wall from collapsing together.
    """
    ops: List[Dict[str, Any]] = []

    pts = []
    for idx, w in enumerate(walls):
        s = tuple(float(c) for c in w["geometry"]["start"])
        e = tuple(float(c) for c in w["geometry"]["end"])
        pts.append((idx, "start", s))
        pts.append((idx, "end", e))

    n = len(pts)
    visited = [False] * n
    clusters: List[List[int]] = []

    for i in range(n):
        if visited[i]:
            continue
        cluster = [i]
        visited[i] = True
        queue = [i]

        while queue:
            curr = queue.pop(0)
            w_curr_idx = pts[curr][0]
            p_curr = pts[curr][2]
            for j in range(n):
                if not visited[j]:
                    w_other_idx = pts[j][0]
                    # Never collapse start and end of the same wall together
                    if w_curr_idx == w_other_idx:
                        continue
                    already_in_cluster_wall_ids = {pts[k][0] for k in cluster}
                    if w_other_idx in already_in_cluster_wall_ids:
                        continue
                    p_other = pts[j][2]
                    if _distance(p_curr, p_other) <= tolerance:
                        visited[j] = True
                        cluster.append(j)
                        queue.append(j)
        clusters.append(cluster)

    for cl in clusters:
        if len(cl) <= 1:
            continue

        coords = [pts[idx][2] for idx in cl]
        avg_x = round(sum(c[0] for c in coords) / len(coords), 2)
        avg_y = round(sum(c[1] for c in coords) / len(coords), 2)
        target = (avg_x, avg_y)

        for pt_idx in cl:
            w_idx, end_type, orig = pts[pt_idx]
            dist = _distance(orig, target)
            if dist > 1e-4:
                w = walls[w_idx]
                w["geometry"][end_type] = list(target)
                w[end_type] = list(target)
                p_s = w["geometry"]["start"]
                p_e = w["geometry"]["end"]
                w["geometry"]["length"] = round(math.hypot(p_e[0] - p_s[0], p_e[1] - p_s[1]), 2)
                ops.append({
                    "type": "snap_endpoint",
                    "severity": "INFO",
                    "wall_id": w["id"],
                    "endpoint": end_type,
                    "original": list(orig),
                    "snapped": list(target),
                    "distance": round(dist, 2)
                })

    return walls, ops


def snap_t_junctions(
    walls: List[Dict[str, Any]],
    tolerance: float = CORNER_SNAP_TOLERANCE
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """Snaps endpoints that meet another wall's body into a clean T-junction."""
    ops: List[Dict[str, Any]] = []

    for i, w1 in enumerate(walls):
        for j, w2 in enumerate(walls):
            if i == j:
                continue
            for ep_type in ["start", "end"]:
                pt = tuple(w1["geometry"][ep_type])
                seg_s = tuple(w2["geometry"]["start"])
                seg_e = tuple(w2["geometry"]["end"])
                if _distance(pt, seg_s) < 1e-3 or _distance(pt, seg_e) < 1e-3:
                    continue
                dist, proj = _point_to_segment_distance(pt, seg_s, seg_e)
                if 1e-4 < dist <= tolerance:
                    d_s = _distance(proj, seg_s)
                    d_e = _distance(proj, seg_e)
                    if d_s > 2.0 and d_e > 2.0:
                        proj_rounded = [round(proj[0], 2), round(proj[1], 2)]
                        w1["geometry"][ep_type] = proj_rounded
                        w1[ep_type] = proj_rounded
                        p_s = w1["geometry"]["start"]
                        p_e = w1["geometry"]["end"]
                        w1["geometry"]["length"] = round(math.hypot(p_e[0] - p_s[0], p_e[1] - p_s[1]), 2)
                        ops.append({
                            "type": "snap_t_junction",
                            "severity": "INFO",
                            "wall_id": w1["id"],
                            "target_wall_id": w2["id"],
                            "endpoint": ep_type,
                            "original": list(pt),
                            "snapped": proj_rounded,
                            "distance": round(dist, 2)
                        })

    return walls, ops


def merge_collinear_walls(
    walls: List[Dict[str, Any]],
    doors: List[Dict[str, Any]],
    windows: List[Dict[str, Any]],
    merge_tol: float = WALL_MERGE_TOLERANCE,
    angle_tol: float = COLINEAR_ANGLE_TOLERANCE_DEG,
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]], Dict[str, str], List[Dict[str, Any]]]:
    """
    Finds collinear fragmented walls separated by door/window gaps and merges them
    into continuous architectural host walls.
    Returns (active_walls, removed_artifacts, wall_reassignment_map, merge_ops).
    """
    merge_ops: List[Dict[str, Any]] = []
    wall_reassignments: Dict[str, str] = {}
    removed_artifacts: List[Dict[str, Any]] = []

    # 1. Identify and retire extraction artifacts (like w9: length < MIN_WALL_LENGTH)
    active_walls: List[Dict[str, Any]] = []
    for w in walls:
        w_len = w["geometry"]["length"]
        # If wall is shorter than MIN_WALL_LENGTH and does not host any door/window directly
        hosts_opening = any(d.get("wall_id") == w["id"] for d in doors) or any(win.get("wall_id") == w["id"] for win in windows)
        if w_len < MIN_WALL_LENGTH and not hosts_opening:
            w_copy = dict(w)
            w_copy["corrected"] = True
            w_copy["correction_reason"] = "extraction_artifact_in_opening_gap"
            removed_artifacts.append(w_copy)
            merge_ops.append({
                "type": "remove_artifact_wall",
                "severity": "INFO",
                "wall_id": w["id"],
                "length": w_len,
                "reason": "Wall is an extraction artifact in an opening gap"
            })
        else:
            active_walls.append(w)

    # 2. Cluster collinear walls
    n = len(active_walls)
    visited = [False] * n
    groups: List[List[int]] = []

    for i in range(n):
        if visited[i]:
            continue
        group = [i]
        visited[i] = True
        queue = [i]

        while queue:
            curr = queue.pop(0)
            w_curr = active_walls[curr]
            for j in range(n):
                if not visited[j]:
                    w_other = active_walls[j]
                    if _are_walls_collinear(w_curr, w_other, angle_tol_deg=angle_tol, dist_tol=merge_tol):
                        visited[j] = True
                        group.append(j)
                        queue.append(j)
        groups.append(group)

    merged_walls: List[Dict[str, Any]] = []

    for grp in groups:
        if len(grp) == 1:
            merged_walls.append(active_walls[grp[0]])
            continue

        # Sort members by primary axis coordinate (X or Y depending on orientation)
        grp_walls = [active_walls[idx] for idx in grp]
        p_ref_s = grp_walls[0]["geometry"]["start"]
        p_ref_e = grp_walls[0]["geometry"]["end"]
        is_horizontal = abs(p_ref_e[0] - p_ref_s[0]) >= abs(p_ref_e[1] - p_ref_s[1])

        # Gather all endpoints
        all_pts = []
        for gw in grp_walls:
            all_pts.append(tuple(gw["geometry"]["start"]))
            all_pts.append(tuple(gw["geometry"]["end"]))

        coord_idx = 0 if is_horizontal else 1
        all_pts.sort(key=lambda pt: pt[coord_idx])

        # New merged start and end are the extremes
        ext_start = list(all_pts[0])
        ext_end = list(all_pts[-1])

        # Primary host wall is the first/longest wall in the group
        grp_walls.sort(key=lambda w: w["geometry"]["length"], reverse=True)
        primary = grp_walls[0]
        primary_id = primary["id"]

        avg_thickness = round(sum(w["geometry"]["thickness"] for w in grp_walls) / len(grp_walls), 2)
        merged_len = round(math.hypot(ext_end[0] - ext_start[0], ext_end[1] - ext_start[1]), 2)

        merged_wall = {
            "id": primary_id,
            "source": primary["source"],
            "source_ids": [w["id"] for w in grp_walls],
            "corrected": True,
            "correction_reason": "merged_collinear_fragments",
            "geometry": {
                "start": ext_start,
                "end": ext_end,
                "thickness": avg_thickness,
                "length": merged_len,
            },
            "start": ext_start,
            "end": ext_end,
            "thickness": avg_thickness,
        }
        merged_walls.append(merged_wall)

        # Track reassignments for openings
        for gw in grp_walls:
            if gw["id"] != primary_id:
                wall_reassignments[gw["id"]] = primary_id
                merge_ops.append({
                    "type": "merge_wall_fragment",
                    "severity": "INFO",
                    "absorbed_wall_id": gw["id"],
                    "target_wall_id": primary_id,
                    "reason": "Merged into continuous architectural host wall"
                })

    return merged_walls, removed_artifacts, wall_reassignments, merge_ops


def clean_topology(
    scene: Dict[str, Any],
    snap_tol: float = TOPOLOGY_SNAP_TOLERANCE,
    corner_tol: float = CORNER_SNAP_TOLERANCE,
    merge_collinear: bool = MERGE_COLLINEAR_FRAGMENTS,
) -> Dict[str, Any]:
    """
    Main topology cleanup pipeline for Member 2.
    """
    cleaned_scene = dict(scene)
    all_ops: List[Dict[str, Any]] = []

    raw_walls = scene.get("walls", [])
    raw_doors = scene.get("doors", [])
    raw_windows = scene.get("windows", [])

    processed_walls: List[Dict[str, Any]] = []
    for w in raw_walls:
        w_id = w["id"]
        p_start = [round(float(w["start"][0]), 2), round(float(w["start"][1]), 2)]
        p_end = [round(float(w["end"][0]), 2), round(float(w["end"][1]), 2)]
        th = float(w.get("thickness", 10.0))
        length = round(math.hypot(p_end[0] - p_start[0], p_end[1] - p_start[1]), 2)

        entry = {
            "id": w_id,
            "source": {
                "start": list(p_start),
                "end": list(p_end),
                "thickness": th
            },
            "geometry": {
                "start": list(p_start),
                "end": list(p_end),
                "thickness": th,
                "length": length
            },
            "start": list(p_start),
            "end": list(p_end),
            "thickness": th
        }
        processed_walls.append(entry)

    # 1. Snap nearly touching endpoints
    processed_walls, snap_ops = snap_endpoints(processed_walls, tolerance=snap_tol)
    all_ops.extend(snap_ops)

    # 2. T-junction corner snapping
    processed_walls, tj_ops = snap_t_junctions(processed_walls, tolerance=corner_tol)
    all_ops.extend(tj_ops)

    # 3. Optional collinear fragment merging & artifact removal
    removed_artifacts: List[Dict[str, Any]] = []
    wall_reassignments: Dict[str, str] = {}
    if merge_collinear:
        processed_walls, removed_artifacts, wall_reassignments, merge_ops = merge_collinear_walls(
            processed_walls, raw_doors, raw_windows,
            merge_tol=WALL_MERGE_TOLERANCE,
            angle_tol=COLINEAR_ANGLE_TOLERANCE_DEG
        )
        all_ops.extend(merge_ops)

        # Snap corners again after merging
        processed_walls, final_snaps = snap_endpoints(processed_walls, tolerance=snap_tol)
        all_ops.extend(final_snaps)
        processed_walls, final_tj = snap_t_junctions(processed_walls, tolerance=corner_tol)
        all_ops.extend(final_tj)

    cleaned_scene["walls"] = processed_walls
    cleaned_scene["removed_walls"] = removed_artifacts
    cleaned_scene["wall_reassignments"] = wall_reassignments
    cleaned_scene["topology_operations"] = all_ops

    return cleaned_scene
