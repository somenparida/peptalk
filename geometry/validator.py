"""
Validation system and Accuracy Report generator for Member 2.

Performs deep structural, relational, and geometric validation on scene.json.
Returns structured error messages and detailed dimension reports.
"""

from __future__ import annotations

import json
import math
from typing import Dict, Any, List, Optional, Tuple
from shapely.geometry import Polygon
from pydantic import ValidationError

from geometry.schema import SceneSpecification, Wall, Door, Window, Room


class ValidationResult:
    def __init__(self):
        self.is_valid: bool = True
        self.errors: List[str] = []
        self.warnings: List[str] = []
        self.spec: Optional[SceneSpecification] = None
        self.report: Dict[str, Any] = {}

    def to_dict(self) -> Dict[str, Any]:
        return {
            "scene_valid": self.is_valid,
            "errors": self.errors,
            "warnings": self.warnings,
            "report": self.report
        }


class SceneValidator:
    """Validates raw JSON or SceneSpecification instances."""

    @staticmethod
    def validate_raw_json(data: Any) -> ValidationResult:
        result = ValidationResult()

        if isinstance(data, str):
            try:
                data = json.loads(data)
            except json.JSONDecodeError as e:
                result.is_valid = False
                result.errors.append(f"Invalid JSON syntax: {e}")
                return result

        if not isinstance(data, dict):
            result.is_valid = False
            result.errors.append(f"Scene data must be a JSON object, got {type(data).__name__}")
            return result

        # 1. Schema Parsing with Pydantic
        try:
            spec = SceneSpecification.model_validate(data)
            result.spec = spec
        except ValidationError as e:
            result.is_valid = False
            for err in e.errors():
                loc = " -> ".join(str(p) for p in err["loc"])
                result.errors.append(f"Schema error at [{loc}]: {err['msg']}")
            return result

        # 2. Relational & Geometric Cross-Validation
        SceneValidator._validate_relationships_and_geometry(spec, result)

        # 3. Generate Accuracy & Dimension Report
        SceneValidator._generate_accuracy_report(spec, result)

        return result

    @staticmethod
    def _validate_relationships_and_geometry(spec: SceneSpecification, result: ValidationResult) -> None:
        # Check uniqueness of IDs
        wall_ids: Dict[str, Wall] = {}
        for w in spec.walls:
            if w.id in wall_ids:
                result.is_valid = False
                result.errors.append(f"Duplicate wall ID '{w.id}' found.")
            wall_ids[w.id] = w

        door_ids: set[str] = set()
        for d in spec.doors:
            if d.id in door_ids:
                result.is_valid = False
                result.errors.append(f"Duplicate door ID '{d.id}' found.")
            door_ids.add(d.id)

        win_ids: set[str] = set()
        for win in spec.windows:
            if win.id in win_ids:
                result.is_valid = False
                result.errors.append(f"Duplicate window ID '{win.id}' found.")
            win_ids.add(win.id)

        room_ids: set[str] = set()
        for r in spec.rooms:
            if r.id in room_ids:
                result.is_valid = False
                result.errors.append(f"Duplicate room ID '{r.id}' found.")
            room_ids.add(r.id)

        # Check door references and bounds
        wall_openings: Dict[str, List[Tuple[float, float, str]]] = {w_id: [] for w_id in wall_ids}

        for d in spec.doors:
            if d.wall_id not in wall_ids:
                result.is_valid = False
                result.errors.append(f"Door '{d.id}' references wall '{d.wall_id}', but '{d.wall_id}' does not exist.")
                continue

            wall = wall_ids[d.wall_id]
            wall_len = wall.length
            effective_wall_height = wall.height or spec.wall_height

            if d.offset + d.width > wall_len + 1e-4:
                result.is_valid = False
                result.errors.append(
                    f"Door '{d.id}' (offset={d.offset:.3f}m, width={d.width:.3f}m) exceeds wall '{d.wall_id}' length ({wall_len:.3f}m)."
                )

            if d.height > effective_wall_height:
                result.is_valid = False
                result.errors.append(
                    f"Door '{d.id}' height ({d.height:.3f}m) exceeds wall height ({effective_wall_height:.3f}m)."
                )

            wall_openings[d.wall_id].append((d.offset, d.offset + d.width, f"door:{d.id}"))

        # Check window references and bounds
        for win in spec.windows:
            if win.wall_id not in wall_ids:
                result.is_valid = False
                result.errors.append(f"Window '{win.id}' references wall '{win.wall_id}', but '{win.wall_id}' does not exist.")
                continue

            wall = wall_ids[win.wall_id]
            wall_len = wall.length
            effective_wall_height = wall.height or spec.wall_height

            if win.offset + win.width > wall_len + 1e-4:
                result.is_valid = False
                result.errors.append(
                    f"Window '{win.id}' (offset={win.offset:.3f}m, width={win.width:.3f}m) exceeds wall '{win.wall_id}' length ({wall_len:.3f}m)."
                )

            if win.sill_height + win.height > effective_wall_height + 1e-4:
                result.is_valid = False
                result.errors.append(
                    f"Window '{win.id}' top height ({win.sill_height + win.height:.3f}m) exceeds wall height ({effective_wall_height:.3f}m)."
                )

            wall_openings[win.wall_id].append((win.offset, win.offset + win.width, f"window:{win.id}"))

        # Check for overlapping openings on each wall
        for w_id, intervals in wall_openings.items():
            intervals.sort(key=lambda item: item[0])
            for i in range(len(intervals) - 1):
                cur_start, cur_end, cur_id = intervals[i]
                next_start, next_end, next_id = intervals[i + 1]
                if cur_end > next_start + 1e-4:
                    result.is_valid = False
                    result.errors.append(
                        f"Wall '{w_id}' has overlapping openings: '{cur_id}' [{cur_start:.2f}-{cur_end:.2f}m] overlaps '{next_id}' [{next_start:.2f}-{next_end:.2f}m]."
                    )

        # Validate room polygons
        for r in spec.rooms:
            coords = r.polygon
            if len(coords) < 3:
                result.is_valid = False
                result.errors.append(f"Room '{r.id}' has fewer than 3 vertices.")
                continue

            poly = Polygon(coords)
            if not poly.is_valid:
                result.is_valid = False
                result.errors.append(f"Room '{r.id}' polygon is geometrically invalid (self-intersecting or degenerate).")
                continue

            if poly.area < 1e-3:
                result.is_valid = False
                result.errors.append(f"Room '{r.id}' polygon has zero or near-zero area ({poly.area:.4f} m²).")
                continue

    @staticmethod
    def _generate_accuracy_report(spec: SceneSpecification, result: ValidationResult) -> None:
        total_floor_area = 0.0
        room_details = []

        for r in spec.rooms:
            poly = Polygon(r.polygon)
            area = float(poly.area) if poly.is_valid else 0.0
            perimeter = float(poly.length) if poly.is_valid else 0.0
            bounds = list(poly.bounds) if poly.is_valid else [0.0, 0.0, 0.0, 0.0]
            total_floor_area += area

            room_details.append({
                "id": r.id,
                "name": r.name or r.id,
                "area_m2": round(area, 4),
                "perimeter_m": round(perimeter, 4),
                "bounding_box": [round(b, 4) for b in bounds],
                "num_vertices": len(r.polygon)
            })

        wall_details = []
        for w in spec.walls:
            dx = w.end[0] - w.start[0]
            dy = w.end[1] - w.start[1]
            angle_deg = math.degrees(math.atan2(dy, dx)) % 360.0
            wall_details.append({
                "id": w.id,
                "length_m": round(w.length, 4),
                "thickness_m": round(w.thickness, 4),
                "height_m": round(w.height or spec.wall_height, 4),
                "orientation_deg": round(angle_deg, 2)
            })

        door_details = []
        for d in spec.doors:
            door_details.append({
                "id": d.id,
                "wall_id": d.wall_id,
                "offset_m": round(d.offset, 4),
                "width_m": round(d.width, 4),
                "height_m": round(d.height, 4)
            })

        window_details = []
        for win in spec.windows:
            window_details.append({
                "id": win.id,
                "wall_id": win.wall_id,
                "offset_m": round(win.offset, 4),
                "width_m": round(win.width, 4),
                "height_m": round(win.height, 4),
                "sill_height_m": round(win.sill_height, 4)
            })

        valid_rooms = len([r for r in spec.rooms if Polygon(r.polygon).is_valid and Polygon(r.polygon).area > 1e-3])
        valid_walls = len([w for w in spec.walls if w.length > 1e-4])
        valid_doors = len(door_details) if result.is_valid else len(door_details) - len([e for e in result.errors if "Door" in e])
        valid_windows = len(window_details) if result.is_valid else len(window_details) - len([e for e in result.errors if "Window" in e])

        result.report = {
            "scene_valid": result.is_valid,
            "units": spec.units,
            "wall_height_default": spec.wall_height,
            "rooms": {
                "total": len(spec.rooms),
                "valid": max(0, valid_rooms),
                "details": room_details
            },
            "walls": {
                "total": len(spec.walls),
                "valid": max(0, valid_walls),
                "details": wall_details
            },
            "doors": {
                "total": len(spec.doors),
                "valid": max(0, valid_doors),
                "details": door_details
            },
            "windows": {
                "total": len(spec.windows),
                "valid": max(0, valid_windows),
                "details": window_details
            },
            "total_floor_area_m2": round(total_floor_area, 4),
            "warnings": result.warnings
        }
