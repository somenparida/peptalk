"""Core geometric and architectural data models for HNX26EPS06."""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
from shapely.geometry import Polygon

from src.config import CONFIG


class OpeningType(str, Enum):
    """Categorization of wall openings."""
    DOOR = "DOOR"
    WINDOW = "WINDOW"


class ValidationLevel(str, Enum):
    """3-Tier validation severity."""
    ERROR = "ERROR"      # Blocking structural issue
    WARNING = "WARNING"  # Boundary / topological notice
    INFO = "INFO"        # Snapping / merging / cleanup audit


@dataclass
class ValidationIssue:
    """Represents a discrete validation message."""
    level: ValidationLevel
    code: str
    message: str
    entity_id: Optional[str] = None
    details: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "level": self.level.value,
            "code": self.code,
            "message": self.message,
            "entity_id": self.entity_id,
            "details": self.details,
        }


@dataclass
class ValidationReport:
    """Aggregated validation findings for the floor plan."""
    issues: List[ValidationIssue] = field(default_factory=list)

    @property
    def has_errors(self) -> bool:
        return any(i.level == ValidationLevel.ERROR for i in self.issues)

    @property
    def error_count(self) -> int:
        return sum(1 for i in self.issues if i.level == ValidationLevel.ERROR)

    @property
    def warning_count(self) -> int:
        return sum(1 for i in self.issues if i.level == ValidationLevel.WARNING)

    @property
    def info_count(self) -> int:
        return sum(1 for i in self.issues if i.level == ValidationLevel.INFO)

    def add(self, level: ValidationLevel, code: str, message: str,
            entity_id: Optional[str] = None, details: Optional[Dict[str, Any]] = None) -> None:
        self.issues.append(
            ValidationIssue(level, code, message, entity_id, details or {})
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "has_errors": self.has_errors,
            "error_count": self.error_count,
            "warning_count": self.warning_count,
            "info_count": self.info_count,
            "issues": [i.to_dict() for i in self.issues],
        }


@dataclass(frozen=True)
class Point2D:
    """Immutable 2D coordinate vector in floor plan space."""
    x: float
    y: float

    def distance_to(self, other: Point2D) -> float:
        return math.hypot(self.x - other.x, self.y - other.y)

    def vector_to(self, other: Point2D) -> Tuple[float, float]:
        return (other.x - self.x, other.y - self.y)

    def as_tuple(self) -> Tuple[float, float]:
        return (self.x, self.y)

    def as_numpy(self) -> np.ndarray:
        return np.array([self.x, self.y], dtype=float)

    def snap_to(self, other: Point2D, tolerance: float) -> Point2D:
        if self.distance_to(other) <= tolerance:
            return other
        return self

    def round(self, decimals: int = 4) -> Point2D:
        return Point2D(round(self.x, decimals), round(self.y, decimals))

    def __add__(self, other: Point2D) -> Point2D:
        return Point2D(self.x + other.x, self.y + other.y)

    def __sub__(self, other: Point2D) -> Point2D:
        return Point2D(self.x - other.x, self.y - other.y)

    def __mul__(self, scalar: float) -> Point2D:
        return Point2D(self.x * scalar, self.y * scalar)


@dataclass
class OpeningInterval:
    """
    Parametric 1D interval along host wall centerline.
    0 <= start_dist < end_dist <= wall_length.
    """
    start_dist: float
    end_dist: float
    opening_type: OpeningType
    id: str = ""
    height: float = 0.0
    sill_height: float = 0.0
    metadata: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.start_dist > self.end_dist:
            self.start_dist, self.end_dist = self.end_dist, self.start_dist
        if self.height <= 0.0:
            if self.opening_type == OpeningType.DOOR:
                self.height = CONFIG.DOOR_HEIGHT
                self.sill_height = 0.0
            else:
                self.height = CONFIG.WINDOW_HEIGHT
                self.sill_height = CONFIG.WINDOW_SILL_HEIGHT

    @property
    def width(self) -> float:
        return max(0.0, self.end_dist - self.start_dist)

    @property
    def center_dist(self) -> float:
        return 0.5 * (self.start_dist + self.end_dist)

    def overlaps(self, other: OpeningInterval, tolerance: float = 1e-4) -> bool:
        return (self.start_dist < other.end_dist - tolerance and
                self.end_dist > other.start_dist + tolerance)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "type": self.opening_type.value,
            "start_dist": round(self.start_dist, 4),
            "end_dist": round(self.end_dist, 4),
            "width": round(self.width, 4),
            "height": round(self.height, 4),
            "sill_height": round(self.sill_height, 4),
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> OpeningInterval:
        return cls(
            start_dist=float(data["start_dist"]),
            end_dist=float(data["end_dist"]),
            opening_type=OpeningType(data.get("type", "DOOR")),
            id=str(data.get("id", "")),
            height=float(data.get("height", 0.0)),
            sill_height=float(data.get("sill_height", 0.0)),
            metadata=dict(data.get("metadata", {})),
        )


@dataclass
class WallEdge:
    """Architectural wall segment connecting two junction points."""
    id: str
    start: Point2D
    end: Point2D
    thickness: float = CONFIG.WALL_THICKNESS
    height: float = CONFIG.WALL_HEIGHT
    openings: List[OpeningInterval] = field(default_factory=list)

    @property
    def length(self) -> float:
        return self.start.distance_to(self.end)

    @property
    def direction(self) -> Tuple[float, float]:
        """Unit tangent vector from start to end."""
        L = self.length
        if L < 1e-7:
            return (1.0, 0.0)
        return ((self.end.x - self.start.x) / L, (self.end.y - self.start.y) / L)

    @property
    def normal(self) -> Tuple[float, float]:
        """Perpendicular 2D normal vector (rotated 90 deg counter-clockwise)."""
        dx, dy = self.direction
        return (-dy, dx)

    @property
    def angle_rad(self) -> float:
        dx = self.end.x - self.start.x
        dy = self.end.y - self.start.y
        return math.atan2(dy, dx)

    @property
    def angle_deg(self) -> float:
        return math.degrees(self.angle_rad) % 360.0

    @property
    def midpoint(self) -> Point2D:
        return Point2D(0.5 * (self.start.x + self.end.x), 0.5 * (self.start.y + self.end.y))

    def point_at_distance(self, distance: float) -> Point2D:
        dx, dy = self.direction
        return Point2D(self.start.x + dx * distance, self.start.y + dy * distance)

    def project_point(self, point: Point2D) -> Tuple[float, float]:
        """
        Projects arbitrary point onto wall axis.
        Returns (parametric_dist_along_wall, perp_signed_distance).
        """
        vx = point.x - self.start.x
        vy = point.y - self.start.y
        dx, dy = self.direction
        nx, ny = self.normal
        t = vx * dx + vy * dy
        d_perp = vx * nx + vy * ny
        return (t, d_perp)

    def add_opening(self, opening: OpeningInterval) -> bool:
        """
        Safely bind opening interval to this wall.
        Clamps to [0, length] and validates non-overlap.
        """
        L = self.length
        if L < 1e-4:
            return False
        clamped_start = max(0.0, min(L, opening.start_dist))
        clamped_end = max(0.0, min(L, opening.end_dist))
        if clamped_end - clamped_start < 0.05:
            return False

        new_opening = OpeningInterval(
            start_dist=clamped_start,
            end_dist=clamped_end,
            opening_type=opening.opening_type,
            id=opening.id or f"{self.id}_op_{len(self.openings)}",
            height=opening.height,
            sill_height=opening.sill_height,
            metadata=opening.metadata,
        )

        for existing in self.openings:
            if existing.overlaps(new_opening):
                return False

        self.openings.append(new_opening)
        self.openings.sort(key=lambda op: op.start_dist)
        return True

    def get_solid_intervals(self) -> List[Tuple[float, float]]:
        """
        Returns list of solid 1D intervals along wall: [(s0, e0), (s1, e1), ...].
        Between openings there is full solid wall from 0 to height.
        """
        L = self.length
        if not self.openings:
            return [(0.0, L)]

        sorted_ops = sorted(self.openings, key=lambda op: op.start_dist)
        solid_intervals: List[Tuple[float, float]] = []
        cur_pos = 0.0

        for op in sorted_ops:
            if op.start_dist > cur_pos + 1e-4:
                solid_intervals.append((cur_pos, op.start_dist))
            cur_pos = max(cur_pos, op.end_dist)

        if cur_pos < L - 1e-4:
            solid_intervals.append((cur_pos, L))

        return solid_intervals

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "start": self.start.as_tuple(),
            "end": self.end.as_tuple(),
            "thickness": round(self.thickness, 4),
            "height": round(self.height, 4),
            "length": round(self.length, 4),
            "openings": [op.to_dict() for op in self.openings],
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> WallEdge:
        w = cls(
            id=str(data["id"]),
            start=Point2D(float(data["start"][0]), float(data["start"][1])),
            end=Point2D(float(data["end"][0]), float(data["end"][1])),
            thickness=float(data.get("thickness", CONFIG.WALL_THICKNESS)),
            height=float(data.get("height", CONFIG.WALL_HEIGHT)),
        )
        for op_data in data.get("openings", []):
            w.add_opening(OpeningInterval.from_dict(op_data))
        return w


@dataclass
class RoomPolygon:
    """Architectural room enclosed by boundary polygon."""
    id: str
    name: str
    points: List[Point2D]
    color: Tuple[int, int, int, int] = CONFIG.COLOR_FLOOR
    metadata: Dict[str, Any] = field(default_factory=dict)

    @property
    def shapely_polygon(self) -> Polygon:
        coords = [p.as_tuple() for p in self.points]
        if len(coords) < 3:
            return Polygon()
        if coords[0] != coords[-1]:
            coords.append(coords[0])
        return Polygon(coords)

    @property
    def area(self) -> float:
        poly = self.shapely_polygon
        return poly.area if poly.is_valid else 0.0

    @property
    def perimeter(self) -> float:
        poly = self.shapely_polygon
        return poly.length if poly.is_valid else 0.0

    @property
    def centroid(self) -> Point2D:
        poly = self.shapely_polygon
        if not poly.is_valid or poly.is_empty:
            if not self.points:
                return Point2D(0.0, 0.0)
            avg_x = sum(p.x for p in self.points) / len(self.points)
            avg_y = sum(p.y for p in self.points) / len(self.points)
            return Point2D(avg_x, avg_y)
        c = poly.centroid
        return Point2D(c.x, c.y)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "points": [p.as_tuple() for p in self.points],
            "area_sq_m": round(self.area, 3),
            "perimeter_m": round(self.perimeter, 3),
            "color": list(self.color),
            "metadata": self.metadata,
        }


@dataclass
class FloorPlan:
    """Complete floor plan representation with topological walls and rooms."""
    walls: List[WallEdge] = field(default_factory=list)
    rooms: List[RoomPolygon] = field(default_factory=list)
    scale: float = 1.0  # meters per coordinate unit
    validation: ValidationReport = field(default_factory=ValidationReport)
    metadata: Dict[str, Any] = field(default_factory=dict)

    @property
    def total_area(self) -> float:
        return sum(r.area for r in self.rooms)

    @property
    def total_wall_length(self) -> float:
        return sum(w.length for w in self.walls)

    @property
    def opening_counts(self) -> Dict[str, int]:
        doors = 0
        windows = 0
        for w in self.walls:
            for op in w.openings:
                if op.opening_type == OpeningType.DOOR:
                    doors += 1
                elif op.opening_type == OpeningType.WINDOW:
                    windows += 1
        return {"doors": doors, "windows": windows, "total": doors + windows}

    def to_dict(self) -> Dict[str, Any]:
        return {
            "scale": self.scale,
            "wall_count": len(self.walls),
            "room_count": len(self.rooms),
            "openings": self.opening_counts,
            "total_area_sq_m": round(self.total_area, 3),
            "total_wall_length_m": round(self.total_wall_length, 3),
            "walls": [w.to_dict() for w in self.walls],
            "rooms": [r.to_dict() for r in self.rooms],
            "validation": self.validation.to_dict(),
            "metadata": self.metadata,
        }
