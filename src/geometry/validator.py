"""3-Tier validation engine for floor plan geometry."""

from __future__ import annotations

from typing import List

from src.config import CONFIG
from src.geometry.graph import WallGraph
from src.models import (
    FloorPlan,
    OpeningType,
    ValidationLevel,
    ValidationReport,
    WallEdge,
)


class FloorPlanValidator:
    """
    Validates architectural floor plans against physical and topological constraints.
    Categorizes all findings into ERROR (blocking), WARNING (notices), and INFO (audit).
    Preserves source geometry when evidence is insufficient, documenting all notices.
    """

    def validate(self, floor_plan: FloorPlan) -> ValidationReport:
        report = floor_plan.validation  # append to existing audit log

        # 1. Structural Checks (ERROR) & Dimensional Consistency
        if not floor_plan.walls:
            report.add(
                ValidationLevel.ERROR,
                "EMPTY_WALLS",
                "Floor plan contains zero walls. 3D reconstruction is not possible.",
            )
            return report

        for wall in floor_plan.walls:
            if wall.length < CONFIG.MIN_WALL_LENGTH:
                report.add(
                    ValidationLevel.ERROR,
                    "WALL_TOO_SHORT",
                    f"Wall '{wall.id}' has length {wall.length:.3f}m < {CONFIG.MIN_WALL_LENGTH}m.",
                    entity_id=wall.id,
                )
            if wall.thickness <= 0.05 or wall.thickness > 0.80:
                report.add(
                    ValidationLevel.WARNING,
                    "UNUSUAL_WALL_THICKNESS",
                    f"Wall '{wall.id}' has non-standard thickness {wall.thickness:.2f}m.",
                    entity_id=wall.id,
                )
            if wall.height < 2.0 or wall.height > 6.0:
                report.add(
                    ValidationLevel.WARNING,
                    "UNUSUAL_WALL_HEIGHT",
                    f"Wall '{wall.id}' has non-standard height {wall.height:.2f}m.",
                    entity_id=wall.id,
                )

            # Opening Checks & Dimensional Validation
            for op in wall.openings:
                if op.start_dist < -1e-4 or op.end_dist > wall.length + 1e-4:
                    report.add(
                        ValidationLevel.ERROR,
                        "OPENING_OUT_OF_BOUNDS",
                        f"Opening '{op.id}' [{op.start_dist:.2f}, {op.end_dist:.2f}] extends outside wall '{wall.id}' [0, {wall.length:.2f}].",
                        entity_id=op.id,
                    )
                if op.sill_height + op.height > wall.height + 1e-3:
                    report.add(
                        ValidationLevel.ERROR,
                        "OPENING_EXCEEDS_WALL_HEIGHT",
                        f"Opening '{op.id}' vertical extent ({op.sill_height + op.height:.2f}m) exceeds host wall height ({wall.height:.2f}m).",
                        entity_id=op.id,
                    )

                if op.opening_type == OpeningType.DOOR:
                    if op.sill_height > 0.05:
                        report.add(
                            ValidationLevel.WARNING,
                            "DOOR_FLOATING_SILL",
                            f"Door '{op.id}' has non-zero sill height {op.sill_height:.2f}m (doors should sit at floor slab level).",
                            entity_id=op.id,
                        )
                    if op.width < 0.60:
                        report.add(
                            ValidationLevel.WARNING,
                            "DOOR_TOO_NARROW",
                            f"Door '{op.id}' width {op.width:.2f}m is abnormally narrow for residential egress (standard: 0.75-1.20m).",
                            entity_id=op.id,
                        )
                    elif op.width > 2.40:
                        report.add(
                            ValidationLevel.WARNING,
                            "DOOR_TOO_WIDE",
                            f"Door '{op.id}' width {op.width:.2f}m exceeds typical double door aperture.",
                            entity_id=op.id,
                        )
                    if op.height < 1.80 or op.height > 2.70:
                        report.add(
                            ValidationLevel.WARNING,
                            "DOOR_HEIGHT_NON_STANDARD",
                            f"Door '{op.id}' height {op.height:.2f}m deviates from standard door clearance (2.00-2.40m).",
                            entity_id=op.id,
                        )
                elif op.opening_type == OpeningType.WINDOW:
                    if op.width < 0.30:
                        report.add(
                            ValidationLevel.WARNING,
                            "WINDOW_TOO_NARROW",
                            f"Window '{op.id}' width {op.width:.2f}m is narrower than standard minimum.",
                            entity_id=op.id,
                        )
                    elif op.width > 4.50:
                        report.add(
                            ValidationLevel.WARNING,
                            "WINDOW_TOO_WIDE",
                            f"Window '{op.id}' width {op.width:.2f}m exceeds typical structural span.",
                            entity_id=op.id,
                        )
                    if op.sill_height < 0.20:
                        report.add(
                            ValidationLevel.INFO,
                            "LOW_SILL_WINDOW",
                            f"Window '{op.id}' has low sill height {op.sill_height:.2f}m (full-height / curtain window).",
                            entity_id=op.id,
                        )

            # Check for overlapping openings on same host wall
            for i in range(len(wall.openings)):
                for j in range(i + 1, len(wall.openings)):
                    if wall.openings[i].overlaps(wall.openings[j]):
                        report.add(
                            ValidationLevel.WARNING,
                            "OPENING_OVERLAP",
                            f"Openings '{wall.openings[i].id}' and '{wall.openings[j].id}' overlap along wall '{wall.id}'.",
                            entity_id=wall.id,
                        )

        # 2. Connectivity & Topological Graph Checks (WARNING / PRESERVATION NOTICES)
        graph = WallGraph()
        graph.build_from_walls(floor_plan.walls)
        degrees = graph.get_junction_degrees()

        dead_ends = graph.get_dead_end_endpoints()
        if dead_ends:
            for wid, pt in dead_ends:
                report.add(
                    ValidationLevel.WARNING,
                    "DEAD_END_WALL",
                    f"Wall '{wid}' terminates at dead-end endpoint ({pt.x:.2f}, {pt.y:.2f}). Preserving source geometry (insufficient evidence to prune or snap).",
                    entity_id=wid,
                    details={"wall_id": wid, "endpoint": pt.as_tuple()},
                )
            report.add(
                ValidationLevel.WARNING,
                "DEAD_END_WALLS",
                f"Floor plan has {len(dead_ends)} dead-end wall endpoints (unconnected floating partitions). Preserved as source geometry.",
            )

        isolated = graph.get_isolated_walls()
        if isolated:
            for w in isolated:
                report.add(
                    ValidationLevel.WARNING,
                    "ISOLATED_WALL",
                    f"Wall '{w.id}' is completely disconnected (dead ends at both endpoints). Preserving source geometry.",
                    entity_id=w.id,
                )

        components = graph.get_connected_components()
        if len(components) > 1:
            report.add(
                ValidationLevel.WARNING,
                "DISCONNECTED_WALL_CLUSTERS",
                f"Wall graph contains {len(components)} disconnected components.",
            )

        # 3. Room Polygon Closure Checks
        if not floor_plan.rooms:
            report.add(
                ValidationLevel.WARNING,
                "NO_ENCLOSED_ROOMS",
                "Floor plan contains no enclosed rooms. Only exterior or open partitions present.",
            )
        for room in floor_plan.rooms:
            if len(room.points) < 3:
                report.add(
                    ValidationLevel.ERROR,
                    "ROOM_TOO_FEW_VERTICES",
                    f"Room '{room.name}' has fewer than 3 boundary vertices.",
                    entity_id=room.id,
                )
            elif not room.shapely_polygon.is_valid:
                report.add(
                    ValidationLevel.ERROR,
                    "ROOM_POLYGON_INVALID",
                    f"Room '{room.name}' boundary polygon is geometrically invalid (self-intersecting).",
                    entity_id=room.id,
                )
            elif room.area < 1.0:
                report.add(
                    ValidationLevel.WARNING,
                    "ROOM_AREA_SUSPICIOUS",
                    f"Room '{room.name}' has very small area {room.area:.2f}m² (< 1.00m²).",
                    entity_id=room.id,
                )

        # 4. Summary Audit (INFO)
        stats = floor_plan.opening_counts
        report.add(
            ValidationLevel.INFO,
            "SCENE_SUMMARY",
            f"Floor plan contains {len(floor_plan.walls)} walls, {len(floor_plan.rooms)} rooms, {stats['doors']} doors, and {stats['windows']} windows. Total floor area: {floor_plan.total_area:.2f}m².",
        )

        return report
