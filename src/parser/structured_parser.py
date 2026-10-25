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

        # Determine scale (meters per coordinate unit)
        plan_scale = float(scale if scale is not None else data.get("scale", 1.0))
        if plan_scale <= 0.0:
            plan_scale = 1.0
            report.add(ValidationLevel.WARNING, "INVALID_SCALE", "Scale must be > 0. Defaulted to 1.0.")

        report.add(
            ValidationLevel.INFO,
            "PARSER_SCALE_SET",
            f"Using scale {plan_scale:.6f} m/unit for {source_name}.",
        )

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
            height = float(w_raw.get("height", CONFIG.WALL_HEIGHT))

            wall = WallEdge(
                id=wid,
                start=start_pt,
                end=end_pt,
                thickness=max(0.05, thickness),
                height=max(1.0, height),
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

        # Ingest separate openings list if provided at top level as a list
        raw_openings_list = data.get("openings", [])
        if isinstance(raw_openings_list, list) and raw_openings_list:
            raw_ops: List[RawOpening] = []
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

            binder = OpeningBinder()
            binder.bind_openings(raw_ops, walls, report=report)

        # Ingest rooms if present
        rooms: List[RoomPolygon] = []
        raw_rooms = data.get("rooms", [])

        for idx, r_raw in enumerate(raw_rooms):
            rid = str(r_raw.get("id", f"room_{idx + 1}"))
            rname = str(r_raw.get("name", f"Room {idx + 1}"))
            pts_raw = r_raw.get("points", [])
            pts = [Point2D(float(p[0]) * plan_scale, float(p[1]) * plan_scale) for p in pts_raw]

            color_raw = r_raw.get("color", CONFIG.COLOR_FLOOR)
            color = (
                int(color_raw[0]),
                int(color_raw[1]),
                int(color_raw[2]),
                int(color_raw[3]) if len(color_raw) > 3 else 255,
            )

            room = RoomPolygon(
                id=rid,
                name=rname,
                points=pts,
                color=color,
                metadata=dict(r_raw.get("metadata", {})),
            )
            rooms.append(room)

        # If rooms not provided, auto-extract from wall topology
        if not rooms and walls:
            room_engine = RoomTopologyEngine()
            rooms = room_engine.extract_rooms_from_walls(walls, report=report)

        floor_plan = FloorPlan(
            walls=walls,
            rooms=rooms,
            scale=plan_scale,
            validation=report,
            metadata=dict(data.get("metadata", {})),
        )

        return floor_plan
