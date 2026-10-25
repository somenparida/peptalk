"""Robust geometric snapping for L-junctions and T-junctions."""

from __future__ import annotations

import math
from typing import List, Optional, Set, Tuple

import numpy as np

from src.config import CONFIG
from src.models import Point2D, ValidationLevel, ValidationReport, WallEdge


class SnappingEngine:
    """
    Cleans up imprecise wall endpoints by:
    1. Clustering endpoints within tolerance to common junction coordinates (L/corner snapping).
    2. Snapping dead-end endpoints near wall bodies onto the wall line (T-junction snapping).
    3. Splitting host walls at T-junction contact points to preserve graph topology.
    """

    def __init__(self, tolerance: float = CONFIG.SNAP_TOLERANCE_METERS) -> None:
        self.tolerance = tolerance

    def snap_endpoints(self, walls: List[WallEdge], report: Optional[ValidationReport] = None) -> List[WallEdge]:
        """
        Group endpoints that fall within tolerance and replace them with cluster centroids.
        """
        if not walls:
            return []

        # Collect all endpoints
        endpoints: List[Tuple[str, str, Point2D]] = []  # (wall_id, 'start'|'end', point)
        for w in walls:
            endpoints.append((w.id, "start", w.start))
            endpoints.append((w.id, "end", w.end))

        n = len(endpoints)
        visited = [False] * n
        snapped_map: dict[Tuple[str, str], Point2D] = {}

        for i in range(n):
            if visited[i]:
                continue
            cluster = [i]
            visited[i] = True
            for j in range(i + 1, n):
                if not visited[j] and endpoints[i][2].distance_to(endpoints[j][2]) <= self.tolerance:
                    cluster.append(j)
                    visited[j] = True

            if len(cluster) > 1:
                # Calculate centroid of cluster
                avg_x = sum(endpoints[idx][2].x for idx in cluster) / len(cluster)
                avg_y = sum(endpoints[idx][2].y for idx in cluster) / len(cluster)
                centroid = Point2D(avg_x, avg_y)

                for idx in cluster:
                    wid, ep_type, orig_pt = endpoints[idx]
                    snapped_map[(wid, ep_type)] = centroid
                    if report and orig_pt.distance_to(centroid) > 1e-4:
                        report.add(
                            ValidationLevel.INFO,
                            "ENDPOINT_SNAPPED",
                            f"Snapped {ep_type} of wall '{wid}' by {orig_pt.distance_to(centroid):.3f}m to ({centroid.x:.2f}, {centroid.y:.2f})",
                            entity_id=wid,
                        )
            else:
                wid, ep_type, pt = endpoints[i]
                snapped_map[(wid, ep_type)] = pt

        # Reconstruct walls with snapped coordinates
        snapped_walls: List[WallEdge] = []
        for w in walls:
            new_start = snapped_map.get((w.id, "start"), w.start)
            new_end = snapped_map.get((w.id, "end"), w.end)
            if new_start.distance_to(new_end) >= CONFIG.MIN_WALL_LENGTH:
                new_w = WallEdge(
                    id=w.id,
                    start=new_start,
                    end=new_end,
                    thickness=w.thickness,
                    height=w.height,
                    openings=list(w.openings),
                )
                snapped_walls.append(new_w)
            elif report:
                report.add(
                    ValidationLevel.WARNING,
                    "WALL_COLLAPSED",
                    f"Wall '{w.id}' collapsed below minimum length after snapping and was pruned.",
                    entity_id=w.id,
                )

        return snapped_walls

    def snap_t_junctions(self, walls: List[WallEdge], report: Optional[ValidationReport] = None) -> List[WallEdge]:
        """
        Identify endpoints landing near the interior of other walls, snap them onto the host wall,
        and split the host wall at the intersection point.
        """
        walls_list = list(walls)
        modified = True
        iteration = 0
        max_iterations = 10

        while modified and iteration < max_iterations:
            modified = False
            iteration += 1

            for i, target_wall in enumerate(walls_list):
                split_point: Optional[Point2D] = None
                split_param: float = 0.0

                for candidate_wall in walls_list:
                    if candidate_wall.id == target_wall.id:
                        continue

                    # Check candidate start & end against target_wall interior
                    for pt, is_start in [(candidate_wall.start, True), (candidate_wall.end, False)]:
                        t, d_perp = target_wall.project_point(pt)
                        # Interior check: distance from endpoints must be > tolerance
                        if self.tolerance < t < (target_wall.length - self.tolerance):
                            if abs(d_perp) <= self.tolerance:
                                # Snap pt onto target wall line
                                proj_pt = target_wall.point_at_distance(t)
                                split_point = proj_pt
                                split_param = t

                                # Update candidate endpoint
                                if is_start:
                                    candidate_wall.start = proj_pt
                                else:
                                    candidate_wall.end = proj_pt

                                if report:
                                    report.add(
                                        ValidationLevel.INFO,
                                        "T_JUNCTION_SNAPPED",
                                        f"Snapped endpoint of wall '{candidate_wall.id}' to interior of '{target_wall.id}' at dist {t:.2f}m",
                                        entity_id=candidate_wall.id,
                                    )
                                break
                    if split_point is not None:
                        break

                if split_point is not None:
                    # Split target_wall into two segments: start -> split_point, split_point -> end
                    part1 = WallEdge(
                        id=f"{target_wall.id}_a",
                        start=target_wall.start,
                        end=split_point,
                        thickness=target_wall.thickness,
                        height=target_wall.height,
                    )
                    part2 = WallEdge(
                        id=f"{target_wall.id}_b",
                        start=split_point,
                        end=target_wall.end,
                        thickness=target_wall.thickness,
                        height=target_wall.height,
                    )

                    # Distribute openings
                    for op in target_wall.openings:
                        if op.end_dist <= split_param:
                            part1.add_opening(op)
                        elif op.start_dist >= split_param:
                            shifted_op = op.__class__(
                                start_dist=op.start_dist - split_param,
                                end_dist=op.end_dist - split_param,
                                opening_type=op.opening_type,
                                id=op.id,
                                height=op.height,
                                sill_height=op.sill_height,
                                metadata=op.metadata,
                            )
                            part2.add_opening(shifted_op)
                        else:
                            # Opening straddles split: split or keep on dominant side
                            if (split_param - op.start_dist) > (op.end_dist - split_param):
                                part1.add_opening(op)
                            else:
                                shifted_op = op.__class__(
                                    start_dist=0.0,
                                    end_dist=op.end_dist - split_param,
                                    opening_type=op.opening_type,
                                    id=op.id,
                                    height=op.height,
                                    sill_height=op.sill_height,
                                    metadata=op.metadata,
                                )
                                part2.add_opening(shifted_op)

                    walls_list.pop(i)
                    walls_list.insert(i, part2)
                    walls_list.insert(i, part1)
                    modified = True
                    break

        return walls_list

    def clean_and_snap(self, walls: List[WallEdge], report: Optional[ValidationReport] = None) -> List[WallEdge]:
        """Runs complete snapping pipeline."""
        walls = self.snap_endpoints(walls, report=report)
        walls = self.snap_t_junctions(walls, report=report)
        walls = self.snap_endpoints(walls, report=report)
        return walls
