"""Room polygon topology extraction, validation, and area computation."""

from __future__ import annotations

from typing import List, Optional, Tuple

import numpy as np
from shapely.geometry import LineString, MultiPolygon, Polygon
from shapely.ops import polygonize, unary_union
from shapely.validation import make_valid

from src.config import CONFIG
from src.models import (
    Point2D,
    RoomPolygon,
    ValidationLevel,
    ValidationReport,
    WallEdge,
)

PALETTE = [
    (238, 232, 222, 255),  # Warm Cream
    (222, 232, 228, 255),  # Soft Sage
    (225, 228, 238, 255),  # Gentle Periwinkle
    (238, 225, 218, 255),  # Light Terracotta
    (232, 235, 220, 255),  # Pale Olive
    (218, 232, 238, 255),  # Ice Blue
    (238, 220, 228, 255),  # Muted Rose
    (228, 224, 216, 255),  # Neutral Linen
]


class RoomTopologyEngine:
    """
    Extracts, validates, and computes geometric properties for architectural rooms.
    Ensures non-self-intersecting 2D boundary polygons and accurate floor areas.
    """

    def __init__(self, min_room_area: float = 1.0) -> None:
        self.min_room_area = min_room_area

    def validate_and_clean_polygon(
        self, points: List[Point2D], report: Optional[ValidationReport] = None, room_id: str = ""
    ) -> Optional[List[Point2D]]:
        """Validates polygon via Shapely, repairing self-intersections if needed."""
        if len(points) < 3:
            if report:
                report.add(
                    ValidationLevel.ERROR,
                    "ROOM_TOO_FEW_VERTICES",
                    f"Room '{room_id}' has fewer than 3 vertices.",
                    entity_id=room_id,
                )
            return None

        coords = [p.as_tuple() for p in points]
        if coords[0] != coords[-1]:
            coords.append(coords[0])

        poly = Polygon(coords)
        if not poly.is_valid:
            if report:
                report.add(
                    ValidationLevel.WARNING,
                    "ROOM_SELF_INTERSECTION",
                    f"Room '{room_id}' has self-intersecting boundary; repairing with make_valid.",
                    entity_id=room_id,
                )
            poly = make_valid(poly)
            if isinstance(poly, MultiPolygon):
                # Pick largest component
                poly = max(poly.geoms, key=lambda g: g.area)

        if not isinstance(poly, Polygon) or poly.area < self.min_room_area:
            if report:
                report.add(
                    ValidationLevel.ERROR,
                    "ROOM_INVALID_AREA",
                    f"Room '{room_id}' area ({poly.area if hasattr(poly, 'area') else 0.0:.2f}m²) is below minimum {self.min_room_area}m².",
                    entity_id=room_id,
                )
            return None

        # Extract cleaned outer boundary
        cleaned_pts = [Point2D(x, y) for x, y in poly.exterior.coords[:-1]]
        return cleaned_pts

    def extract_rooms_from_walls(
        self, walls: List[WallEdge], report: Optional[ValidationReport] = None
    ) -> List[RoomPolygon]:
        """
        Topologically recovers enclosed room polygons by polygonizing the wall graph centerline network.
        Filters out exterior unbounded regions.
        """
        if not walls:
            return []

        # Convert wall edges to shapely LineStrings
        lines = []
        for w in walls:
            if w.length >= CONFIG.MIN_WALL_LENGTH:
                lines.append(LineString([w.start.as_tuple(), w.end.as_tuple()]))

        if not lines:
            return []

        # Polygonize
        union_lines = unary_union(lines)
        detected_polys = list(polygonize(union_lines))

        if not detected_polys:
            if report:
                report.add(
                    ValidationLevel.WARNING,
                    "NO_ROOMS_FOUND",
                    "No enclosed rooms could be polygonized from current wall network.",
                )
            return []

        # Calculate bounding box of entire wall set to identify if any polygon is exterior
        all_coords = []
        for w in walls:
            all_coords.extend([w.start.as_tuple(), w.end.as_tuple()])
        xs = [c[0] for c in all_coords]
        ys = [c[1] for c in all_coords]
        total_bbox_area = (max(xs) - min(xs)) * (max(ys) - min(ys))

        rooms: List[RoomPolygon] = []
        color_idx = 0

        for i, poly in enumerate(detected_polys):
            # Ignore tiny artifact faces or giant exterior faces
            if poly.area < self.min_room_area:
                continue
            if poly.area >= 0.95 * total_bbox_area and len(detected_polys) > 1:
                # Likely outer enclosure
                continue

            pts = [Point2D(x, y) for x, y in poly.exterior.coords[:-1]]
            room_id = f"room_{i + 1}"
            room_name = f"Room {i + 1}"
            color = PALETTE[color_idx % len(PALETTE)]
            color_idx += 1

            room = RoomPolygon(
                id=room_id,
                name=room_name,
                points=pts,
                color=color,
                metadata={"detected_from": "wall_polygonization"},
            )

            rooms.append(room)
            if report:
                report.add(
                    ValidationLevel.INFO,
                    "ROOM_EXTRACTED",
                    f"Discovered enclosed '{room_name}' with area {room.area:.2f}m² and perimeter {room.perimeter:.2f}m.",
                    entity_id=room_id,
                )

        return rooms
