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
    """

    def validate(self, floor_plan: FloorPlan) -> ValidationReport:
        report = floor_plan.validation  # append to existing audit log

        # 1. Structural Checks (ERROR)
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
            if wall.thickness <= 0.02 or wall.thickness > 1.0:
                report.add(
                    ValidationLevel.WARNING,
                    "UNUSUAL_WALL_THICKNESS",
                    f"Wall '{wall.id}' has non-standard thickness {wall.thickness:.2f}m.",
                    entity_id=wall.id,
                )

            # Opening Checks
            for op in wall.openings:
                if op.start_dist < 0.0 or op.end_dist > wall.length + 1e-3:
                    report.add(
                        ValidationLevel.ERROR,
                        "OPENING_OUT_OF_BOUNDS",
                        f"Opening '{op.id}' [{op.start_dist:.2f}, {op.end_dist:.2f}] extends outside wall '{wall.id}' [0, {wall.length:.2f}].",
                        entity_id=op.id,
                    )
                if op.width < 0.20:
                    report.add(
                        ValidationLevel.WARNING,
                        "OPENING_TOO_NARROW",
                        f"Opening '{op.id}' width {op.width:.2f}m is abnormally narrow.",
                        entity_id=op.id,
                    )
                if op.width > 3.5:
                    report.add(
                        ValidationLevel.WARNING,
                        "OPENING_TOO_WIDE",
                        f"Opening '{op.id}' width {op.width:.2f}m exceeds typical single aperture size.",
                        entity_id=op.id,
                    )

        # 2. Connectivity & Topological Graph Checks (WARNING)
        graph = WallGraph()
        graph.build_from_walls(floor_plan.walls)
        degrees = graph.get_junction_degrees()

        if degrees["dead_end"] > 0:
            report.add(
                ValidationLevel.WARNING,
                "DEAD_END_WALLS",
                f"Floor plan has {degrees['dead_end']} dead-end wall endpoints (unconnected floating partitions).",
            )

        components = graph.get_connected_components()
        if len(components) > 1:
            report.add(
                ValidationLevel.WARNING,
                "DISCONNECTED_WALL_CLUSTERS",
                f"Wall graph contains {len(components)} disconnected components.",
            )

        # 3. Room Polygon Checks
        for room in floor_plan.rooms:
            if room.area < 1.0:
                report.add(
                    ValidationLevel.WARNING,
                    "ROOM_AREA_SUSPICIOUS",
                    f"Room '{room.name}' has very small area {room.area:.2f}m².",
                    entity_id=room.id,
                )
            if not room.shapely_polygon.is_valid:
                report.add(
                    ValidationLevel.ERROR,
                    "ROOM_POLYGON_INVALID",
                    f"Room '{room.name}' boundary polygon is geometrically invalid.",
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
