"""
Pydantic schema definitions and validation for scene.json.

Defines the core interface contract between Member 1 (Blueprint Parser)
and Member 2 (3D Scene Generation).
"""

from __future__ import annotations

import math
from typing import List, Optional, Tuple, Dict, Any, Literal
from pydantic import BaseModel, Field, field_validator, model_validator


def _check_finite_coord(val: float, name: str = "coordinate") -> float:
    if not math.isfinite(val):
        raise ValueError(f"{name} must be a finite number (got {val})")
    if abs(val) > 10000.0:
        raise ValueError(f"{name} value {val} is outside reasonable architectural range [-10000, 10000]")
    return float(val)


class CoordinateSystem(BaseModel):
    up_axis: Literal["Z", "Y"] = Field(
        default="Z",
        description="Vertical axis in 3D space. Standard Member 2 convention is 'Z'."
    )
    horizontal_axes: List[Literal["X", "Y", "Z"]] = Field(
        default=["X", "Y"],
        description="Horizontal plane axes. Standard Member 2 convention is ['X', 'Y']."
    )

    @field_validator("horizontal_axes")
    @classmethod
    def validate_axes(cls, v: List[str]) -> List[str]:
        if len(v) != 2:
            raise ValueError("horizontal_axes must contain exactly 2 axes, e.g. ['X', 'Y']")
        if v[0] == v[1]:
            raise ValueError("horizontal_axes cannot repeat the same axis")
        return v


class Wall(BaseModel):
    id: str = Field(..., min_length=1, description="Unique identifier for the wall")
    start: Tuple[float, float] = Field(..., description="2D start point [x, y] in meters")
    end: Tuple[float, float] = Field(..., description="2D end point [x, y] in meters")
    thickness: float = Field(0.15, gt=0.0, le=2.0, description="Wall thickness in meters (0 < t <= 2m)")
    height: Optional[float] = Field(
        None,
        gt=0.0,
        le=20.0,
        description="Wall height in meters. If omitted, uses global scene wall_height."
    )

    @field_validator("start", "end")
    @classmethod
    def validate_points(cls, pt: Tuple[float, float]) -> Tuple[float, float]:
        if len(pt) != 2:
            raise ValueError("Wall coordinates must be a 2D [x, y] pair")
        x = _check_finite_coord(pt[0], "Wall X")
        y = _check_finite_coord(pt[1], "Wall Y")
        return (x, y)

    @model_validator(mode="after")
    def validate_wall_geometry(self) -> Wall:
        dx = self.end[0] - self.start[0]
        dy = self.end[1] - self.start[1]
        length = math.hypot(dx, dy)
        if length < 1e-4:
            raise ValueError(f"Wall '{self.id}' has zero or near-zero length ({length:.6f}m)")
        return self

    @property
    def length(self) -> float:
        return math.hypot(self.end[0] - self.start[0], self.end[1] - self.start[1])


class Door(BaseModel):
    id: str = Field(..., min_length=1, description="Unique identifier for the door")
    wall_id: str = Field(..., min_length=1, description="ID of the wall containing this door")
    offset: float = Field(
        ...,
        ge=0.0,
        description="Distance in meters from wall start along wall vector to the door start"
    )
    width: float = Field(..., gt=0.0, le=10.0, description="Door opening width in meters")
    height: float = Field(2.1, gt=0.0, le=10.0, description="Door opening height in meters")

    @field_validator("offset", "width", "height")
    @classmethod
    def check_dimensions(cls, v: float) -> float:
        return _check_finite_coord(v, "Door dimension")


class Window(BaseModel):
    id: str = Field(..., min_length=1, description="Unique identifier for the window")
    wall_id: str = Field(..., min_length=1, description="ID of the wall containing this window")
    offset: float = Field(
        ...,
        ge=0.0,
        description="Distance in meters from wall start along wall vector to the window start"
    )
    width: float = Field(..., gt=0.0, le=15.0, description="Window opening width in meters")
    height: float = Field(..., gt=0.0, le=10.0, description="Window opening height in meters")
    sill_height: float = Field(
        0.9,
        ge=0.0,
        le=10.0,
        description="Sill height from floor level z=0 in meters"
    )

    @field_validator("offset", "width", "height", "sill_height")
    @classmethod
    def check_dimensions(cls, v: float) -> float:
        return _check_finite_coord(v, "Window dimension")


class Room(BaseModel):
    id: str = Field(..., min_length=1, description="Unique identifier for the room")
    name: Optional[str] = Field(None, description="Human-readable room name, e.g. 'Living Room'")
    polygon: List[Tuple[float, float]] = Field(
        ...,
        min_length=3,
        description="List of 2D [x, y] coordinates forming the room polygon boundary in meters"
    )

    @field_validator("polygon")
    @classmethod
    def validate_polygon_vertices(cls, poly: List[Tuple[float, float]]) -> List[Tuple[float, float]]:
        if len(poly) < 3:
            raise ValueError(f"Room polygon must contain at least 3 vertices (got {len(poly)})")
        if len(poly) > 1000:
            raise ValueError(f"Room polygon contains too many vertices ({len(poly)} > 1000)")
        validated = []
        for i, pt in enumerate(poly):
            if len(pt) != 2:
                raise ValueError(f"Room polygon vertex index {i} must be a 2D [x, y] pair")
            x = _check_finite_coord(pt[0], f"Room vertex {i} X")
            y = _check_finite_coord(pt[1], f"Room vertex {i} Y")
            validated.append((x, y))
        return validated


class SceneSpecification(BaseModel):
    units: str = Field(
        default="meters",
        description="Measurement units. Standard is 'meters' (or 'm')."
    )
    coordinate_system: CoordinateSystem = Field(
        default_factory=CoordinateSystem,
        description="Coordinate system conventions (default up_axis='Z', horizontal=['X', 'Y'])"
    )
    wall_height: float = Field(
        default=2.8,
        gt=0.5,
        le=20.0,
        description="Default wall height in meters across the scene"
    )
    walls: List[Wall] = Field(default_factory=list, description="List of architectural walls")
    doors: List[Door] = Field(default_factory=list, description="List of doors / openings")
    windows: List[Window] = Field(default_factory=list, description="List of windows / openings")
    rooms: List[Room] = Field(default_factory=list, description="List of room polygon definitions")
    metadata: Dict[str, Any] = Field(
        default_factory=dict,
        description="Arbitrary blueprint metadata (source, designer, scale, date)"
    )

    @field_validator("units")
    @classmethod
    def validate_units(cls, u: str) -> str:
        u_lower = u.lower().strip()
        if u_lower not in ["meters", "meter", "m"]:
            raise ValueError(
                f"Unsupported units '{u}'. Member 2 operates in metric 'meters' (or 'm'). "
                f"Please convert or use the adapter before 3D generation."
            )
        return "meters"
