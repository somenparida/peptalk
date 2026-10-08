"""
Phase 5 & 6: Scene Normalization and Pipeline Orchestration Module for Member 2.

Integrates validation, topology cleanup, opening resolution, room analysis,
and scale conversion into the canonical validated_scene.json specification.
"""

from __future__ import annotations

import copy
from typing import Dict, Any, Optional, Tuple

from geometry.config import (
    DEFAULT_WALL_HEIGHT_METERS,
    DEFAULT_DOOR_HEIGHT_METERS,
    DEFAULT_WINDOW_SILL_HEIGHT_METERS,
    DEFAULT_WINDOW_HEIGHT_METERS,
    WALL_SNAP_TOLERANCE,
    CORNER_SNAP_TOLERANCE,
)
from geometry.validator import validate_scene
from geometry.topology import clean_topology
from geometry.openings import process_openings
from geometry.rooms import process_rooms
from geometry.scale import convert_to_metric


def normalize_scene(
    raw_scene: Dict[str, Any],
    meters_per_pixel: Optional[float] = None,
    scale_source: str = "explicit",
    scale_confidence: float = 1.0,
    snap_tol: float = WALL_SNAP_TOLERANCE,
    corner_tol: float = CORNER_SNAP_TOLERANCE,
) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    """
    Main Member 2 pipeline execution.
    Takes raw scene dict and returns (validated_scene, validation_report).
    """
    # 1. Initial Validation on raw input
    initial_report = validate_scene(raw_scene)

    # 2. Topology Cleanup (Snapping, Gaps, Provenance)
    cleaned_scene = clean_topology(raw_scene, snap_tol=snap_tol, corner_tol=corner_tol)
    cleaned_walls = cleaned_scene["walls"]
    walls_map = {w["id"]: w for w in cleaned_walls}

    # 3. Process Openings with explicit geometry
    raw_doors = raw_scene.get("doors", [])
    raw_windows = raw_scene.get("windows", [])
    doors, windows, opening_issues = process_openings(raw_doors, raw_windows, walls_map)

    # 4. Process Rooms
    raw_rooms = raw_scene.get("rooms", [])
    rooms, room_issues = process_rooms(raw_rooms)

    # 5. Build base structured output
    img_meta = raw_scene.get("image", {"width": 512, "height": 260})

    normalized: Dict[str, Any] = {
        "version": "1.0",
        "units": "pixels",
        "coordinate_system": "image",
        "image": {
            "width": img_meta.get("width", 512),
            "height": img_meta.get("height", 260)
        },
        "scale": {
            "meters_per_pixel": None,
            "source": "unknown",
            "confidence": 0.0,
            "metric_available": False
        },
        "defaults": {
            "wall_height": DEFAULT_WALL_HEIGHT_METERS,
            "door_height": DEFAULT_DOOR_HEIGHT_METERS,
            "window_sill_height": DEFAULT_WINDOW_SILL_HEIGHT_METERS,
            "window_height": DEFAULT_WINDOW_HEIGHT_METERS
        },
        "walls": cleaned_walls,
        "doors": doors,
        "windows": windows,
        "rooms": rooms,
        "topology_operations": cleaned_scene.get("topology_operations", []),
    }

    # 6. Optional Metric Conversion
    if meters_per_pixel is not None and meters_per_pixel > 0:
        normalized = convert_to_metric(
            normalized,
            meters_per_pixel=meters_per_pixel,
            source=scale_source,
            confidence=scale_confidence
        )

    # 7. Final Validation on normalized output
    final_report = validate_scene(normalized)
    final_report["issues"].extend(opening_issues)
    final_report["issues"].extend(room_issues)

    normalized["validation"] = {
        "valid": final_report["valid"],
        "issues": final_report["issues"]
    }

    return normalized, final_report
