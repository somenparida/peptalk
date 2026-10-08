"""
Phase 2: Topology Cleanup Module for Member 2.

Handles endpoint snapping, corner junctions, small gap detection, and collinear segment analysis.
Preserves stable IDs and full traceability to source geometry.
"""

from __future__ import annotations

import math
from typing import Dict, Any, List, Tuple, Optional
import numpy as np

from geometry.config import (
    WALL_SNAP_TOLERANCE,
    WALL_MERGE_TOLERANCE,
    COLINEAR_ANGLE_TOLERANCE_DEG,
    CORNER_SNAP_TOLERANCE,
)


def _distance(p1: Tuple[float, float], p2: Tuple[float, float]) -> float:
    return math.hypot(p1[0] - p2[0], p1[1] - p2[1])


def _point_to_segment_distance(
    pt: Tuple[float, float],
    seg_start: Tuple[float, float],
    seg_end: Tuple[float, float]
) -> Tuple[float, Tuple[float, float]]:
    """Returns distance from pt to line segment, and the closest point on segment."""
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


def snap_endpoints(
    walls: List[Dict[str, Any]],
    tolerance: float = WALL_SNAP_TOLERANCE
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """
    Finds clusters of wall endpoints within tolerance and snaps them to cluster centroids.
    Returns (cleaned_walls, list_of_operations).
    """
    ops: List[Dict[str, Any]] = []

    # Gather all endpoints
    # items: list of (wall_index, 'start'/'end', [x, y])
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
                    # Never collapse the start and end of the SAME wall together
                    if w_curr_idx == w_other_idx:
                        continue
                    # Check if another endpoint of w_other_idx is already in cluster
                    already_in_cluster_wall_ids = {pts[k][0] for k in cluster}
                    if w_other_idx in already_in_cluster_wall_ids:
                        continue
                    p_other = pts[j][2]
                    if _distance(p_curr, p_other) <= tolerance:
                        visited[j] = True
                        cluster.append(j)
                        queue.append(j)
        clusters.append(cluster)

    # For each cluster with >1 endpoint, snap to centroid
    for cl in clusters:
        if len(cl) <= 1:
            continue

        # Check if endpoints belong to different walls (or different endpoints)
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
                w[end_type] = list(target)  # sync top-level
                # recalculate length
                p_s = w["geometry"]["start"]
                p_e = w["geometry"]["end"]
                w["geometry"]["length"] = round(math.hypot(p_e[0] - p_s[0], p_e[1] - p_s[1]), 2)
                ops.append({
                    "type": "snap_endpoint",
                    "wall_id": w["id"],
                    "endpoint": end_type,
                    "original": list(orig),
                    "snapped": list(target),
                    "distance": round(dist, 2)
                })

    return walls, ops


def clean_topology(
    scene: Dict[str, Any],
    snap_tol: float = WALL_SNAP_TOLERANCE,
    corner_tol: float = CORNER_SNAP_TOLERANCE,
) -> Dict[str, Any]:
    """
    Main topology cleanup pipeline.
    Constructs cleaned walls while strictly preserving source metadata and stable IDs.
    """
    cleaned_scene = dict(scene)
    all_ops: List[Dict[str, Any]] = []

    raw_walls = scene.get("walls", [])
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
            # Top-level mirrors geometry for convenience
            "start": list(p_start),
            "end": list(p_end),
            "thickness": th
        }
        processed_walls.append(entry)

    # 1. Snap nearly touching endpoints
    processed_walls, snap_ops = snap_endpoints(processed_walls, tolerance=snap_tol)
    all_ops.extend(snap_ops)

    # 2. Check for T-junction corner snapping (endpoint within corner_tol of another wall line)
    for i, w1 in enumerate(processed_walls):
        for j, w2 in enumerate(processed_walls):
            if i == j:
                continue
            for ep_type in ["start", "end"]:
                pt = tuple(w1["geometry"][ep_type])
                seg_s = tuple(w2["geometry"]["start"])
                seg_e = tuple(w2["geometry"]["end"])
                # Don't snap if pt is already equal to seg endpoints
                if _distance(pt, seg_s) < 1e-3 or _distance(pt, seg_e) < 1e-3:
                    continue
                dist, proj = _point_to_segment_distance(pt, seg_s, seg_e)
                # Only snap if within tolerance and genuinely interior to the segment
                if 1e-4 < dist <= corner_tol:
                    # check projection is not near endpoints
                    d_s = _distance(proj, seg_s)
                    d_e = _distance(proj, seg_e)
                    if d_s > 2.0 and d_e > 2.0:
                        proj_rounded = [round(proj[0], 2), round(proj[1], 2)]
                        w1["geometry"][ep_type] = proj_rounded
                        w1[ep_type] = proj_rounded
                        p_s = w1["geometry"]["start"]
                        p_e = w1["geometry"]["end"]
                        w1["geometry"]["length"] = round(math.hypot(p_e[0] - p_s[0], p_e[1] - p_s[1]), 2)
                        all_ops.append({
                            "type": "snap_t_junction",
                            "wall_id": w1["id"],
                            "target_wall_id": w2["id"],
                            "endpoint": ep_type,
                            "original": list(pt),
                            "snapped": proj_rounded,
                            "distance": round(dist, 2)
                        })

    cleaned_scene["walls"] = processed_walls
    cleaned_scene["topology_operations"] = all_ops
    return cleaned_scene
