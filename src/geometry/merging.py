"""Collinear wall segment detection and merging engine."""

from __future__ import annotations

import math
from typing import List, Optional, Tuple

from src.config import CONFIG
from src.models import (
    OpeningInterval,
    Point2D,
    ValidationLevel,
    ValidationReport,
    WallEdge,
)


class CollinearWallMerger:
    """
    Detects collinear wall fragments (such as segments separated by door/window gaps or
    subdivided during drafting) and merges them into clean, continuous architectural host walls.
    Maintains and re-parameterizes existing opening intervals along the merged centerline.
    """

    def __init__(
        self,
        max_angle_deg: float = CONFIG.COLLINEAR_ANGLE_MAX_DEG,
        max_offset: float = CONFIG.COLLINEAR_MAX_DISTANCE,
        max_gap: float = 2.4,  # allow bridging standard door/window apertures (up to ~2.4m)
    ) -> None:
        self.max_angle_deg = max_angle_deg
        self.max_offset = max_offset
        self.max_gap = max_gap

    def are_collinear(self, w1: WallEdge, w2: WallEdge) -> Tuple[bool, float, float, float, float]:
        """
        Tests if two walls are collinear and returns:
        (is_collinear, p1_start_t, p1_end_t, p2_start_t, p2_end_t)
        where t is the 1D projection coordinate along the axis of w1.
        """
        # Direction check (0 or 180 degrees)
        d1x, d1y = w1.direction
        d2x, d2y = w2.direction
        dot = d1x * d2x + d1y * d2y
        cross = abs(d1x * d2y - d1y * d2x)

        # Angle check
        angle_diff_deg = math.degrees(math.asin(min(1.0, cross)))
        if angle_diff_deg > self.max_angle_deg:
            return False, 0.0, 0.0, 0.0, 0.0

        # Project w2 endpoints onto w1 line
        t2_s, perp2_s = w1.project_point(w2.start)
        t2_e, perp2_e = w1.project_point(w2.end)

        if abs(perp2_s) > self.max_offset or abs(perp2_e) > self.max_offset:
            return False, 0.0, 0.0, 0.0, 0.0

        # Parametric intervals along w1 line
        t1_s, t1_e = 0.0, w1.length
        min_w2_t = min(t2_s, t2_e)
        max_w2_t = max(t2_s, t2_e)

        # Check gap between [t1_s, t1_e] and [min_w2_t, max_w2_t]
        gap = max(0.0, max(min_w2_t - t1_e, t1_s - max_w2_t))
        if gap > self.max_gap:
            return False, 0.0, 0.0, 0.0, 0.0

        return True, t1_s, t1_e, t2_s, t2_e

    def merge_pair(self, w1: WallEdge, w2: WallEdge) -> Optional[WallEdge]:
        """Merges two collinear walls into one host wall if compatible."""
        is_collinear, t1_s, t1_e, t2_s, t2_e = self.are_collinear(w1, w2)
        if not is_collinear:
            return None

        # Determine extreme extents along w1 axis
        all_t = [(t1_s, w1.start), (t1_e, w1.end),
                 (t2_s, w2.start), (t2_e, w2.end)]
        all_t.sort(key=lambda item: item[0])

        new_start = all_t[0][1]
        new_end = all_t[-1][1]
        min_t = all_t[0][0]
        max_t = all_t[-1][0]
        new_length = max_t - min_t

        if new_length < CONFIG.MIN_WALL_LENGTH:
            return None

        merged_id = f"{w1.id}_merged_{w2.id}"
        merged_wall = WallEdge(
            id=merged_id,
            start=new_start,
            end=new_end,
            thickness=max(w1.thickness, w2.thickness),
            height=max(w1.height, w2.height),
        )

        # Re-map openings from w1 onto merged wall
        for op in w1.openings:
            world_s = w1.point_at_distance(op.start_dist)
            world_e = w1.point_at_distance(op.end_dist)
            new_s_t, _ = merged_wall.project_point(world_s)
            new_e_t, _ = merged_wall.project_point(world_e)
            re_op = OpeningInterval(
                start_dist=min(new_s_t, new_e_t),
                end_dist=max(new_s_t, new_e_t),
                opening_type=op.opening_type,
                id=op.id,
                height=op.height,
                sill_height=op.sill_height,
                metadata=op.metadata,
            )
            merged_wall.add_opening(re_op)

        # Re-map openings from w2 onto merged wall
        for op in w2.openings:
            world_s = w2.point_at_distance(op.start_dist)
            world_e = w2.point_at_distance(op.end_dist)
            new_s_t, _ = merged_wall.project_point(world_s)
            new_e_t, _ = merged_wall.project_point(world_e)
            re_op = OpeningInterval(
                start_dist=min(new_s_t, new_e_t),
                end_dist=max(new_s_t, new_e_t),
                opening_type=op.opening_type,
                id=op.id,
                height=op.height,
                sill_height=op.sill_height,
                metadata=op.metadata,
            )
            merged_wall.add_opening(re_op)

        return merged_wall

    def merge_all(self, walls: List[WallEdge], report: Optional[ValidationReport] = None) -> List[WallEdge]:
        """
        Iteratively finds and merges collinear pairs until convergence,
        then prunes any redundant subset walls.
        """
        current_walls = list(walls)
        merged = True
        pass_num = 0

        while merged and pass_num < 200:
            merged = False
            pass_num += 1
            n = len(current_walls)

            for i in range(n):
                for j in range(i + 1, n):
                    w1 = current_walls[i]
                    w2 = current_walls[j]

                    candidate = self.merge_pair(w1, w2)
                    if candidate is not None:
                        if report:
                            report.add(
                                ValidationLevel.INFO,
                                "COLLINEAR_MERGED",
                                f"Merged collinear walls '{w1.id}' and '{w2.id}' into '{candidate.id}' (length: {candidate.length:.2f}m)",
                                entity_id=candidate.id,
                            )
                        # Replace w1 and w2 with merged wall
                        current_walls.pop(j)
                        current_walls.pop(i)
                        current_walls.append(candidate)
                        merged = True
                        break
                if merged:
                    break

        # Post-merge deduplication: prune any residual redundant subset walls
        current_walls = self.deduplicate_walls(current_walls, report=report)

        return current_walls

    def deduplicate_walls(
        self, walls: List[WallEdge], report: Optional[ValidationReport] = None
    ) -> List[WallEdge]:
        """
        Removes any wall that is substantially contained within another collinear wall,
        preserving and transferring all openings to the surviving host wall.
        """
        current = list(walls)
        to_remove = set()
        n = len(current)

        for i in range(n):
            if i in to_remove:
                continue
            w1 = current[i]
            for j in range(i + 1, n):
                if j in to_remove:
                    continue
                w2 = current[j]

                # Angular collinearity check
                ang_diff = abs(w1.angle_deg - w2.angle_deg)
                if ang_diff > 180:
                    ang_diff = 360 - ang_diff
                if ang_diff > self.max_angle_deg and abs(ang_diff - 180) > self.max_angle_deg:
                    continue

                t1_s, d1_s = w2.project_point(w1.start)
                t1_e, d1_e = w2.project_point(w1.end)
                if max(abs(d1_s), abs(d1_e)) > self.max_offset:
                    continue

                min_t, max_t = min(t1_s, t1_e), max(t1_s, t1_e)
                ov = min(w2.length, max_t) - max(0.0, min_t)
                w1_len = max(1e-4, w1.length)
                w2_len = max(1e-4, w2.length)

                if ov / w1_len > 0.85:
                    # w1 is contained within w2: transfer openings to w2 and prune w1
                    for op in w1.openings:
                        pt_s = w1.point_at_distance(op.start_dist)
                        pt_e = w1.point_at_distance(op.end_dist)
                        s_t, _ = w2.project_point(pt_s)
                        e_t, _ = w2.project_point(pt_e)
                        re_op = OpeningInterval(
                            start_dist=min(s_t, e_t),
                            end_dist=max(s_t, e_t),
                            opening_type=op.opening_type,
                            id=op.id,
                            height=op.height,
                            sill_height=op.sill_height,
                            metadata=op.metadata,
                        )
                        w2.add_opening(re_op)
                    to_remove.add(i)
                    if report:
                        report.add(
                            ValidationLevel.INFO,
                            "WALL_DEDUPLICATED",
                            f"Pruned redundant subset wall '{w1.id}' contained within '{w2.id}'.",
                            entity_id=w1.id,
                        )
                    break
                elif ov / w2_len > 0.85:
                    # w2 is contained within w1: transfer openings to w1 and prune w2
                    for op in w2.openings:
                        pt_s = w2.point_at_distance(op.start_dist)
                        pt_e = w2.point_at_distance(op.end_dist)
                        s_t, _ = w1.project_point(pt_s)
                        e_t, _ = w1.project_point(pt_e)
                        re_op = OpeningInterval(
                            start_dist=min(s_t, e_t),
                            end_dist=max(s_t, e_t),
                            opening_type=op.opening_type,
                            id=op.id,
                            height=op.height,
                            sill_height=op.sill_height,
                            metadata=op.metadata,
                        )
                        w1.add_opening(re_op)
                    to_remove.add(j)
                    if report:
                        report.add(
                            ValidationLevel.INFO,
                            "WALL_DEDUPLICATED",
                            f"Pruned redundant subset wall '{w2.id}' contained within '{w1.id}'.",
                            entity_id=w2.id,
                        )

        return [w for idx, w in enumerate(current) if idx not in to_remove]
