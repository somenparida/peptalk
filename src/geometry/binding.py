"""Opening interval binding engine for doors and windows."""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

from src.config import CONFIG
from src.models import (
    OpeningInterval,
    OpeningType,
    Point2D,
    ValidationLevel,
    ValidationReport,
    WallEdge,
)


@dataclass
class RawOpening:
    """Raw opening observation from CV detector or structured parser."""
    position: Point2D
    width: float
    opening_type: OpeningType
    id: str = ""
    direction: Optional[Tuple[float, float]] = None
    height: float = 0.0
    sill_height: float = 0.0
    metadata: Dict[str, Any] = None  # type: ignore

    def __post_init__(self) -> None:
        if self.metadata is None:
            self.metadata = {}
        if self.height <= 0.0:
            if self.opening_type == OpeningType.DOOR:
                self.height = CONFIG.DOOR_HEIGHT
                self.sill_height = 0.0
            else:
                self.height = CONFIG.WINDOW_HEIGHT
                self.sill_height = CONFIG.WINDOW_SILL_HEIGHT


class OpeningBinder:
    """
    Binds raw opening detections strictly onto host wall segments as 1D parametric intervals:
    [offset - width/2, offset + width/2] where 0 <= start < end <= wall_length.
    """

    def __init__(self, max_projection_distance: float = 0.50) -> None:
        self.max_projection_distance = max_projection_distance

    def find_best_host_wall(
        self, opening: RawOpening, walls: List[WallEdge]
    ) -> Optional[Tuple[WallEdge, float, float]]:
        """
        Finds the closest wall segment to the opening position.
        Returns: (best_wall, t_dist_along_wall, perp_dist) or None.
        """
        best_wall: Optional[WallEdge] = None
        best_perp_dist = float("inf")
        best_t = 0.0

        for wall in walls:
            if wall.length < 1e-4:
                continue

            t, d_perp = wall.project_point(opening.position)
            abs_perp = abs(d_perp)

            # Check if projection is within wall longitudinal bounds with small margin
            margin = opening.width * 0.5
            if -margin <= t <= wall.length + margin:
                # Direction alignment check if opening has direction vector
                if opening.direction is not None:
                    odx, ody = opening.direction
                    wdx, wdy = wall.direction
                    dot = abs(odx * wdx + ody * wdy)
                    # If opening has known direction, it should be roughly parallel to wall
                    if dot < 0.707:  # > 45 deg angle difference
                        continue

                # Effective distance considering wall thickness
                effective_dist = max(0.0, abs_perp - wall.thickness * 0.5)
                if effective_dist < self.max_projection_distance and effective_dist < best_perp_dist:
                    best_perp_dist = effective_dist
                    best_wall = wall
                    best_t = t

        if best_wall is not None:
            return best_wall, best_t, best_perp_dist
        return None

    def bind_openings(
        self,
        raw_openings: List[RawOpening],
        walls: List[WallEdge],
        report: Optional[ValidationReport] = None,
    ) -> Tuple[int, int]:
        """
        Binds a list of raw openings onto the provided walls.
        Returns (bound_count, unbound_count).
        """
        bound_count = 0
        unbound_count = 0

        for idx, raw_op in enumerate(raw_openings):
            op_id = raw_op.id or f"op_{raw_op.opening_type.value.lower()}_{idx + 1}"
            res = self.find_best_host_wall(raw_op, walls)

            if res is None:
                unbound_count += 1
                if report:
                    report.add(
                        ValidationLevel.WARNING,
                        "UNBOUND_OPENING",
                        f"Could not bind {raw_op.opening_type.value} '{op_id}' at ({raw_op.position.x:.2f}, {raw_op.position.y:.2f}) to any wall within {self.max_projection_distance:.2f}m.",
                        entity_id=op_id,
                    )
                continue

            host_wall, t_center, perp_dist = res
            half_w = raw_op.width * 0.5

            # Calculate parametric interval [start_dist, end_dist] with endpoint shift
            if host_wall.length >= raw_op.width:
                start_dist = max(0.0, min(host_wall.length - raw_op.width, t_center - half_w))
                end_dist = start_dist + raw_op.width
            else:
                start_dist = 0.0
                end_dist = host_wall.length

            # Check if opening interval is valid
            if end_dist - start_dist < 0.20:
                unbound_count += 1
                if report:
                    report.add(
                        ValidationLevel.WARNING,
                        "OPENING_TOO_NARROW",
                        f"{raw_op.opening_type.value} '{op_id}' on wall '{host_wall.id}' has width {end_dist - start_dist:.2f}m < minimum 0.2m.",
                        entity_id=op_id,
                    )
                continue

            interval = OpeningInterval(
                start_dist=start_dist,
                end_dist=end_dist,
                opening_type=raw_op.opening_type,
                id=op_id,
                height=raw_op.height,
                sill_height=raw_op.sill_height,
                metadata=raw_op.metadata,
            )

            success = host_wall.add_opening(interval)
            if success:
                bound_count += 1
                if report:
                    report.add(
                        ValidationLevel.INFO,
                        "OPENING_BOUND",
                        f"Bound {raw_op.opening_type.value} '{op_id}' to wall '{host_wall.id}' at interval [{start_dist:.2f}m, {end_dist:.2f}m].",
                        entity_id=op_id,
                    )
            else:
                unbound_count += 1
                if report:
                    report.add(
                        ValidationLevel.WARNING,
                        "OPENING_OVERLAP",
                        f"{raw_op.opening_type.value} '{op_id}' overlaps an existing opening on wall '{host_wall.id}'.",
                        entity_id=op_id,
                    )

        return bound_count, unbound_count
