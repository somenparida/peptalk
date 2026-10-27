"""Structured architectural floor plan parser for JSON and dictionary definitions."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

from src.config import CONFIG
from src.geometry.binding import OpeningBinder, RawOpening
from src.geometry.rooms import RoomTopologyEngine
from src.models import (
    FloorPlan,
    OpeningInterval,
    OpeningType,
    Point2D,
    RoomPolygon,
    ValidationLevel,
    ValidationReport,
    WallEdge,
)


class StructuredFloorPlanParser:
    """
    Parses structured architectural floor plan files (JSON or Python dicts).
    Supports both direct parametric definitions and vertex-edge graph formats.
    """

    def parse_file(self, file_path: Union[str, Path], scale: Optional[float] = None) -> FloorPlan:
        path = Path(file_path)
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return self.parse_dict(data, scale=scale, source_name=path.name)

    def parse_dict(
        self, data: Dict[str, Any], scale: Optional[float] = None, source_name: str = "structured_input"
    ) -> FloorPlan:
        report = ValidationReport()

        # Check if wrapped in benchmark structure
        if "floor_plan" in data:
            data = data["floor_plan"]

        # Parse units and scale factor
        units = str(data.get("units", "m")).lower().strip()
        unit_scale_factors = {
            "m": 1.0,
            "meter": 1.0,
            "meters": 1.0,
            "mm": 0.001,
            "millimeter": 0.001,
            "millimeters": 0.001,
            "cm": 0.01,
            "centimeter": 0.01,
            "centimeters": 0.01,
            "in": 0.0254,
            "inch": 0.0254,
            "inches": 0.0254,
            "ft": 0.3048,
            "foot": 0.3048,
            "feet": 0.3048,
        }
        unit_mult = unit_scale_factors.get(units, 1.0)

        # Determine scale (meters per coordinate unit)
        if scale is not None:
            plan_scale = float(scale)
        else:
            plan_scale = float(data.get("scale", 1.0)) * unit_mult

        if plan_scale <= 0.0:
            plan_scale = 1.0
            report.add(ValidationLevel.WARNING, "INVALID_SCALE", "Scale must be > 0. Defaulted to 1.0.")

        report.add(
            ValidationLevel.INFO,
            "PARSER_SCALE_SET",
            f"Using scale {plan_scale:.6f} m/unit for {source_name} (units: '{units}').",
        )

        global_wall_height = float(data.get("wall_height", CONFIG.WALL_HEIGHT))

        walls: List[WallEdge] = []
        raw_walls = data.get("walls", [])

        for idx, w_raw in enumerate(raw_walls):
            wid = str(w_raw.get("id", f"wall_{idx + 1}"))
            s_coords = w_raw.get("start", [0.0, 0.0])
            e_coords = w_raw.get("end", [0.0, 0.0])

            start_pt = Point2D(float(s_coords[0]) * plan_scale, float(s_coords[1]) * plan_scale)
            end_pt = Point2D(float(e_coords[0]) * plan_scale, float(e_coords[1]) * plan_scale)

            thickness = float(w_raw.get("thickness", CONFIG.WALL_THICKNESS)) * (
                plan_scale if w_raw.get("thickness_in_pixels", False) else 1.0
            )
            height = float(w_raw.get("height", global_wall_height))

            wall = WallEdge(
                id=wid,
                start=start_pt,
                end=end_pt,
                thickness=max(0.05, thickness),
                height=max(1.0, height),
                metadata=dict(w_raw.get("metadata", {})),
            )

            # Ingest wall-attached openings if present
            for op_raw in w_raw.get("openings", []):
                op_type_str = str(op_raw.get("type", "DOOR")).upper()
                op_type = OpeningType.WINDOW if "WINDOW" in op_type_str else OpeningType.DOOR
                s_dist = float(op_raw.get("start_dist", 0.0)) * (
                    plan_scale if op_raw.get("in_pixels", False) else 1.0
                )
                e_dist = float(op_raw.get("end_dist", 0.0)) * (
                    plan_scale if op_raw.get("in_pixels", False) else 1.0
                )
                op_h = float(op_raw.get("height", 0.0))
                op_sill = float(op_raw.get("sill_height", 0.0))

                opening = OpeningInterval(
                    start_dist=s_dist,
                    end_dist=e_dist,
                    opening_type=op_type,
                    id=str(op_raw.get("id", f"{wid}_op")),
                    height=op_h,
                    sill_height=op_sill,
                    metadata=dict(op_raw.get("metadata", {})),
                )
                wall.add_opening(opening)

            walls.append(wall)

        walls_by_id = {w.id: w for w in walls}
        raw_ops: List[RawOpening] = []

        # Ingest top-level doors (scene.schema.json format)
        for idx, d_data in enumerate(data.get("doors", [])):
            if not isinstance(d_data, dict):
                continue
            wid = str(d_data.get("wall_id", ""))
            w_width = float(d_data.get("width", CONFIG.DOOR_WIDTH_DEFAULT)) * plan_scale
            w_height = float(d_data.get("height", CONFIG.DOOR_HEIGHT))
            w_offset = float(d_data.get("offset", 0.0)) * plan_scale
            op_id = str(d_data.get("id", f"door_{idx + 1}"))
            op_meta = dict(d_data.get("metadata", {}))

            if wid and wid in walls_by_id:
                wall = walls_by_id[wid]
                opening = OpeningInterval(
                    start_dist=w_offset,
                    end_dist=w_offset + w_width,
                    opening_type=OpeningType.DOOR,
                    id=op_id,
                    height=w_height,
                    sill_height=0.0,
                    metadata=op_meta,
                )
                wall.add_opening(opening)
            elif "position" in d_data:
                pos_raw = d_data["position"]
                pos = Point2D(float(pos_raw[0]) * plan_scale, float(pos_raw[1]) * plan_scale)
                raw_ops.append(
                    RawOpening(
                        position=pos,
                        width=w_width,
                        opening_type=OpeningType.DOOR,
                        id=op_id,
                        height=w_height,
                        sill_height=0.0,
                        metadata=op_meta,
                    )
                )

        # Ingest top-level windows (scene.schema.json format)
        for idx, w_data in enumerate(data.get("windows", [])):
            if not isinstance(w_data, dict):
                continue
            wid = str(w_data.get("wall_id", ""))
            w_width = float(w_data.get("width", CONFIG.WINDOW_WIDTH_DEFAULT)) * plan_scale
            w_height = float(w_data.get("height", CONFIG.WINDOW_HEIGHT))
            w_offset = float(w_data.get("offset", 0.0)) * plan_scale
            w_sill = float(w_data.get("sill_height", CONFIG.WINDOW_SILL_HEIGHT))
            op_id = str(w_data.get("id", f"window_{idx + 1}"))
            op_meta = dict(w_data.get("metadata", {}))

            if wid and wid in walls_by_id:
                wall = walls_by_id[wid]
                opening = OpeningInterval(
                    start_dist=w_offset,
                    end_dist=w_offset + w_width,
                    opening_type=OpeningType.WINDOW,
                    id=op_id,
                    height=w_height,
                    sill_height=w_sill,
                    metadata=op_meta,
                )
                wall.add_opening(opening)
            elif "position" in w_data:
                pos_raw = w_data["position"]
                pos = Point2D(float(pos_raw[0]) * plan_scale, float(pos_raw[1]) * plan_scale)
                raw_ops.append(
                    RawOpening(
                        position=pos,
                        width=w_width,
                        opening_type=OpeningType.WINDOW,
                        id=op_id,
                        height=w_height,
                        sill_height=w_sill,
                        metadata=op_meta,
                    )
                )

        # Ingest separate openings list if provided at top level as a list
        raw_openings_list = data.get("openings", [])
        if isinstance(raw_openings_list, list) and raw_openings_list:
            for idx, op_data in enumerate(raw_openings_list):
                if not isinstance(op_data, dict):
                    continue
                pos_raw = op_data.get("position", [0.0, 0.0])
                pos = Point2D(float(pos_raw[0]) * plan_scale, float(pos_raw[1]) * plan_scale)
                width = float(op_data.get("width", 1.0)) * (
                    plan_scale if op_data.get("in_pixels", False) else 1.0
                )
                op_type_str = str(op_data.get("type", "DOOR")).upper()
                op_type = OpeningType.WINDOW if "WINDOW" in op_type_str else OpeningType.DOOR

                raw_ops.append(
                    RawOpening(
                        position=pos,
                        width=width,
                        opening_type=op_type,
                        id=str(op_data.get("id", f"opening_{idx + 1}")),
                        height=float(op_data.get("height", 0.0)),
                        sill_height=float(op_data.get("sill_height", 0.0)),
                        metadata=dict(op_data.get("metadata", {})),
                    )
                )

        if raw_ops:
            binder = OpeningBinder()
            binder.bind_openings(raw_ops, walls, report=report)

        # Ingest rooms if present
        room_engine = RoomTopologyEngine(min_room_area=1.0)
        rooms: List[RoomPolygon] = []
        raw_rooms = data.get("rooms", [])

        for idx, r_raw in enumerate(raw_rooms):
            rid = str(r_raw.get("id", f"room_{idx + 1}"))
            rname = str(r_raw.get("name", f"Room {idx + 1}"))
            pts_raw = r_raw.get("points") or r_raw.get("polygon", [])
            pts = [Point2D(float(p[0]) * plan_scale, float(p[1]) * plan_scale) for p in pts_raw]

            color_raw = r_raw.get("color", CONFIG.COLOR_FLOOR)
            color = (
                int(color_raw[0]),
                int(color_raw[1]),
                int(color_raw[2]),
                int(color_raw[3]) if len(color_raw) > 3 else 255,
            )

            # Validate and clean polygon boundary using RoomTopologyEngine
            cleaned_pts = room_engine.validate_and_clean_polygon(pts, report=report, room_id=rid)
            if cleaned_pts is not None and len(cleaned_pts) >= 3:
                room = RoomPolygon(
                    id=rid,
                    name=rname,
                    points=cleaned_pts,
                    color=color,
                    metadata=dict(r_raw.get("metadata", {})),
                )
                rooms.append(room)

        # If rooms not provided, auto-extract from wall topology
        if not rooms and walls:
            rooms = room_engine.extract_rooms_from_walls(walls, report=report)

        metadata = dict(data.get("metadata", {}))

        floor_plan = FloorPlan(
            walls=walls,
            rooms=rooms,
            scale=plan_scale,
            validation=report,
            metadata=metadata,
        )


        return floor_plan
