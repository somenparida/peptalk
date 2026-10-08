"""
Phase 5 & 6: Scene Normalization and Pipeline Orchestration Module for Member 2.

Integrates validation, topology cleanup, opening resolution, room analysis,
and scale conversion into the canonical validated_scene.json specification.
"""

from __future__ import annotations

import copy
from typing import Dict, Any, Optional, Tuple, List

from geometry.config import (
    DEFAULT_WALL_HEIGHT_METERS,
    DEFAULT_DOOR_HEIGHT_METERS,
    DEFAULT_WINDOW_SILL_HEIGHT_METERS,
    DEFAULT_WINDOW_HEIGHT_METERS,
    WALL_SNAP_TOLERANCE,
    CORNER_SNAP_TOLERANCE,
    MERGE_COLLINEAR_FRAGMENTS,
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
    merge_collinear: bool = MERGE_COLLINEAR_FRAGMENTS,
) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    """
    Main Member 2 pipeline execution.
    Takes raw scene dict and returns (validated_scene, validation_report).
    """
    # 1. Initial Validation on raw input
    initial_report = validate_scene(raw_scene)

    # 2. Topology Cleanup (Snapping, Merging, Gaps, Artifacts)
    cleaned_scene = clean_topology(
        raw_scene,
        snap_tol=snap_tol,
        corner_tol=corner_tol,
        merge_collinear=merge_collinear
    )
    cleaned_walls = cleaned_scene["walls"]
    walls_map = {w["id"]: w for w in cleaned_walls}
    reassignments = cleaned_scene.get("wall_reassignments", {})
    raw_walls_map = {w["id"]: w for w in raw_scene.get("walls", [])}

    # 3. Process Openings with explicit geometry and host-wall remapping
    raw_doors = raw_scene.get("doors", [])
    raw_windows = raw_scene.get("windows", [])
    doors, windows, opening_issues = process_openings(
        doors_data=raw_doors,
        windows_data=raw_windows,
        walls_map=walls_map,
        wall_reassignments=reassignments,
        raw_walls_map=raw_walls_map
    )

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
        "removed_walls": cleaned_scene.get("removed_walls", []),
        "wall_reassignments": reassignments,
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

    # Merge auxiliary issues from processing into final report
    existing_keys = {(i["type"], i.get("element_id"), i.get("severity")) for i in final_report["issues"]}
    for aux_iss in opening_issues + room_issues:
        key = (aux_iss["type"], aux_iss.get("element_id"), aux_iss.get("severity"))
        if key not in existing_keys:
            final_report["issues"].append(aux_iss)
            existing_keys.add(key)

    # Re-bucket and update summary
    final_report["errors"] = [i for i in final_report["issues"] if i["severity"].upper() == "ERROR"]
    final_report["warnings"] = [i for i in final_report["issues"] if i["severity"].upper() == "WARNING"]
    final_report["info"] = [i for i in final_report["issues"] if i["severity"].upper() == "INFO"]
    has_errors = len(final_report["errors"]) > 0
    final_report["valid"] = not has_errors
    final_report["status"] = "FAIL" if has_errors else "PASS"

    final_report["summary"] = {
        "status": final_report["status"],
        "wall_count": len(cleaned_walls),
        "door_count": len(doors),
        "window_count": len(windows),
        "room_count": len(rooms),
        "error_count": len(final_report["errors"]),
        "warning_count": len(final_report["warnings"]),
        "info_count": len(final_report["info"]),
        "topology_snaps": len(cleaned_scene.get("topology_operations", [])),
    }
    final_report["stats"] = final_report["summary"]

    normalized["validation"] = {
        "status": final_report["status"],
        "valid": final_report["valid"],
        "errors": final_report["errors"],
        "warnings": final_report["warnings"],
        "info": final_report["info"],
        "summary": final_report["summary"]
    }

    return normalized, final_report
