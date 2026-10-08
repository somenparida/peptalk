"""
Adapter module for Member 1 and external format normalization.

Converts various raw blueprint parser schemas, unit variations (mm, cm, ft, in),
and coordinate systems into the canonical SceneSpecification required by Member 2.
"""

from __future__ import annotations

from typing import Dict, Any, List
from geometry.schema import SceneSpecification, Wall, Door, Window, Room, CoordinateSystem


class SceneAdapter:
    """Normalizes arbitrary blueprint parser outputs into SceneSpecification."""

    UNIT_SCALE_TO_METERS = {
        "meters": 1.0,
        "meter": 1.0,
        "m": 1.0,
        "centimeters": 0.01,
        "centimeter": 0.01,
        "cm": 0.01,
        "millimeters": 0.001,
        "millimeter": 0.001,
        "mm": 0.001,
        "feet": 0.3048,
        "foot": 0.3048,
        "ft": 0.3048,
        "inches": 0.0254,
        "inch": 0.0254,
        "in": 0.0254,
    }

    @classmethod
    def normalize(cls, raw: Dict[str, Any]) -> SceneSpecification:
        """
        Normalizes a raw dictionary into a standardized SceneSpecification.
        Supports:
        - Unit conversion (mm, cm, inches, feet -> meters)
        - Nested walls (openings declared inside wall objects)
        - Coordinate format variations (dict points, flat point arrays)
        - Inverted Y-axis from image/blueprint space
        """
        # 1. Determine unit scale factor
        raw_units = str(raw.get("units", "meters")).lower().strip()
        scale = cls.UNIT_SCALE_TO_METERS.get(raw_units, 1.0)
        custom_scale = raw.get("scale_factor", 1.0)
        total_scale = scale * custom_scale

        wall_height = float(raw.get("wall_height", 2.8)) * total_scale

        # 2. Coordinate system mapping
        coord_sys_raw = raw.get("coordinate_system", {})
        up_axis = coord_sys_raw.get("up_axis", "Z")
        horiz_axes = coord_sys_raw.get("horizontal_axes", ["X", "Y"])
        invert_y = bool(raw.get("invert_y_axis", False))

        def transform_point(p: Any) -> tuple[float, float]:
            if isinstance(p, dict):
                x = float(p.get("x", 0.0))
                y = float(p.get("y", 0.0))
            elif isinstance(p, (list, tuple)) and len(p) >= 2:
                x = float(p[0])
                y = float(p[1])
            else:
                raise ValueError(f"Cannot parse point coordinate: {p}")

            x = x * total_scale
            y = y * total_scale
            if invert_y:
                y = -y
            return (round(x, 6), round(y, 6))

        # 3. Walls
        walls: List[Wall] = []
        doors: List[Door] = []
        windows: List[Window] = []

        for w_data in raw.get("walls", []):
            w_id = str(w_data.get("id", f"wall_{len(walls)+1}"))
            
            # Start and End points
            if "start" in w_data and "end" in w_data:
                start = transform_point(w_data["start"])
                end = transform_point(w_data["end"])
            elif "points" in w_data and len(w_data["points"]) >= 2:
                start = transform_point(w_data["points"][0])
                end = transform_point(w_data["points"][1])
            elif "bbox" in w_data:
                # [x1, y1, x2, y2]
                b = w_data["bbox"]
                start = transform_point([b[0], b[1]])
                end = transform_point([b[2], b[3]])
            else:
                raise ValueError(f"Wall '{w_id}' missing start/end or points specification")

            thickness = float(w_data.get("thickness", 0.15)) * total_scale
            w_h = w_data.get("height")
            if w_h is not None:
                w_h = float(w_h) * total_scale

            walls.append(Wall(
                id=w_id,
                start=start,
                end=end,
                thickness=thickness,
                height=w_h
            ))

            # Handle nested doors/windows if provided inside wall object
            for d_sub in w_data.get("doors", []):
                doors.append(Door(
                    id=str(d_sub.get("id", f"{w_id}_door_{len(doors)+1}")),
                    wall_id=w_id,
                    offset=float(d_sub.get("offset", 0.0)) * total_scale,
                    width=float(d_sub.get("width", 0.9)) * total_scale,
                    height=float(d_sub.get("height", 2.1)) * total_scale,
                ))

            for win_sub in w_data.get("windows", []):
                windows.append(Window(
                    id=str(win_sub.get("id", f"{w_id}_win_{len(windows)+1}")),
                    wall_id=w_id,
                    offset=float(win_sub.get("offset", 0.0)) * total_scale,
                    width=float(win_sub.get("width", 1.2)) * total_scale,
                    height=float(win_sub.get("height", 1.2)) * total_scale,
                    sill_height=float(win_sub.get("sill_height", 0.9)) * total_scale,
                ))

        # 4. Top-level Doors & Windows
        for d_data in raw.get("doors", []):
            doors.append(Door(
                id=str(d_data.get("id", f"door_{len(doors)+1}")),
                wall_id=str(d_data["wall_id"]),
                offset=float(d_data.get("offset", 0.0)) * total_scale,
                width=float(d_data["width"]) * total_scale,
                height=float(d_data.get("height", 2.1)) * total_scale,
            ))

        for win_data in raw.get("windows", []):
            windows.append(Window(
                id=str(win_data.get("id", f"window_{len(windows)+1}")),
                wall_id=str(win_data["wall_id"]),
                offset=float(win_data.get("offset", 0.0)) * total_scale,
                width=float(win_data["width"]) * total_scale,
                height=float(win_data["height"]) * total_scale,
                sill_height=float(win_data.get("sill_height", 0.9)) * total_scale,
            ))

        # 5. Rooms
        rooms: List[Room] = []
        for r_data in raw.get("rooms", []):
            r_id = str(r_data.get("id", f"room_{len(rooms)+1}"))
            r_name = r_data.get("name")
            poly_raw = r_data.get("polygon", [])
            polygon_pts = [transform_point(p) for p in poly_raw]
            rooms.append(Room(
                id=r_id,
                name=r_name,
                polygon=polygon_pts
            ))

        return SceneSpecification(
            units="meters",
            coordinate_system=CoordinateSystem(
                up_axis="Z",
                horizontal_axes=["X", "Y"]
            ),
            wall_height=wall_height,
            walls=walls,
            doors=doors,
            windows=windows,
            rooms=rooms,
            metadata=raw.get("metadata", {})
        )
