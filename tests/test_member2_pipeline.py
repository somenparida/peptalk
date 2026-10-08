"""
Member 2 Comprehensive Automated Test Suite.
Covers all required test categories and criteria from Section 19:
- WALLS: valid wall, zero-length wall, invalid thickness, short wall, disconnected wall, wall snapping, wall merging
- DOORS: valid door, missing wall reference, door outside wall, door at wall boundary, door wider than wall, door center calculation, opening interval calculation
- WINDOWS: valid window, missing wall reference, window outside wall, window wider than wall, window center calculation, opening interval calculation
- SCALE: known scale, unknown scale, pixel coordinates preserved, metric conversion
- ROOMS: valid polygon, invalid polygon, self-intersecting polygon, room/wall consistency
- PIPELINE: full Member 1 -> Member 2 validation and correction on actual scene.json
"""

import json
import math
from pathlib import Path
import pytest

from geometry.validator import validate_scene
from geometry.topology import clean_topology, snap_endpoints, merge_collinear_walls
from geometry.openings import process_openings, _compute_canonical_opening
from geometry.rooms import process_rooms
from geometry.scale import convert_to_metric, estimate_scale_from_reference
from geometry.normalize import normalize_scene


# ==============================================================================
# 1. WALL TESTS
# ==============================================================================

def test_wall_valid():
    scene = {
        "walls": [{"id": "w1", "start": [0.0, 0.0], "end": [100.0, 0.0], "thickness": 10.0}]
    }
    report = validate_scene(scene)
    assert report["valid"] is True
    assert report["status"] == "PASS"
    assert len(report["errors"]) == 0


def test_wall_zero_length():
    scene = {
        "walls": [{"id": "w_zero", "start": [50.0, 50.0], "end": [50.0, 50.0], "thickness": 10.0}]
    }
    report = validate_scene(scene)
    assert report["valid"] is False
    assert report["status"] == "FAIL"
    assert any(i["type"] == "zero_length_wall" for i in report["errors"])


def test_wall_invalid_thickness():
    scene_neg = {
        "walls": [{"id": "w1", "start": [0.0, 0.0], "end": [100.0, 0.0], "thickness": -5.0}]
    }
    report = validate_scene(scene_neg)
    assert report["valid"] is False
    assert any(i["type"] == "invalid_thickness" for i in report["errors"])

    scene_nan = {
        "walls": [{"id": "w1", "start": [0.0, 0.0], "end": [100.0, 0.0], "thickness": "invalid"}]
    }
    report_nan = validate_scene(scene_nan)
    assert report_nan["valid"] is False
    assert any(i["type"] == "invalid_thickness" for i in report_nan["errors"])


def test_wall_short():
    scene = {
        "walls": [{"id": "w_short", "start": [0.0, 0.0], "end": [10.0, 0.0], "thickness": 10.0}]
    }
    report = validate_scene(scene)
    # Short wall is a WARNING, not an ERROR
    assert report["valid"] is True
    assert any(i["type"] == "short_wall" and i["severity"] == "WARNING" for i in report["warnings"])


def test_wall_disconnected():
    scene = {
        "walls": [
            {"id": "w1", "start": [0.0, 0.0], "end": [100.0, 0.0], "thickness": 10.0},
            {"id": "w_isolated", "start": [500.0, 500.0], "end": [600.0, 500.0], "thickness": 10.0}
        ]
    }
    report = validate_scene(scene)
    assert any(i["type"] == "disconnected_wall" and i["element_id"] == "w_isolated" for i in report["warnings"])


def test_wall_snapping():
    walls = [
        {"id": "w1", "start": [0.0, 0.0], "end": [98.0, 0.0], "thickness": 10.0, "geometry": {"start": [0.0, 0.0], "end": [98.0, 0.0]}},
        {"id": "w2", "start": [102.0, 0.0], "end": [102.0, 50.0], "thickness": 10.0, "geometry": {"start": [102.0, 0.0], "end": [102.0, 50.0]}}
    ]
    snapped, ops = snap_endpoints(walls, tolerance=10.0)
    w1_end = snapped[0]["geometry"]["end"]
    w2_start = snapped[1]["geometry"]["start"]
    assert math.isclose(w1_end[0], w2_start[0], abs_tol=1e-2)
    assert math.isclose(w1_end[1], w2_start[1], abs_tol=1e-2)
    assert len(ops) >= 2


def test_wall_merging():
    # Two collinear walls separated by a gap (e.g. door opening)
    walls = [
        {"id": "w_left", "source": {}, "geometry": {"start": [0.0, 0.0], "end": [50.0, 0.0], "thickness": 10.0, "length": 50.0}},
        {"id": "w_right", "source": {}, "geometry": {"start": [80.0, 0.0], "end": [200.0, 0.0], "thickness": 10.0, "length": 120.0}}
    ]
    merged, removed, reassign, ops = merge_collinear_walls(walls, doors=[], windows=[], merge_tol=15.0, angle_tol=8.0)
    assert len(merged) == 1
    assert merged[0]["id"] in ["w_left", "w_right"]
    assert merged[0]["geometry"]["start"] == [0.0, 0.0]
    assert merged[0]["geometry"]["end"] == [200.0, 0.0]
    assert math.isclose(merged[0]["geometry"]["length"], 200.0, abs_tol=1e-2)


# ==============================================================================
# 2. DOOR TESTS
# ==============================================================================

def test_door_valid():
    scene = {
        "walls": [{"id": "w1", "start": [0.0, 0.0], "end": [200.0, 0.0], "thickness": 10.0}],
        "doors": [{"id": "d1", "wall_id": "w1", "position": 0.5, "width": 30.0}]
    }
    report = validate_scene(scene)
    assert report["valid"] is True
    assert len(report["errors"]) == 0


def test_door_missing_wall_reference():
    scene = {
        "walls": [{"id": "w1", "start": [0.0, 0.0], "end": [100.0, 0.0], "thickness": 10.0}],
        "doors": [{"id": "d1", "wall_id": "non_existent_wall", "position": 0.5, "width": 20.0}]
    }
    report = validate_scene(scene)
    assert report["valid"] is False
    assert any(i["type"] == "missing_wall_reference" for i in report["errors"])


def test_door_outside_wall():
    # Wall length 50, door at offset 45 with width 30 extends to 60 (past 50)
    scene = {
        "walls": [{"id": "w1", "start": [0.0, 0.0], "end": [50.0, 0.0], "thickness": 10.0}],
        "doors": [{"id": "d1", "wall_id": "w1", "offset": 45.0, "width": 30.0}]
    }
    report = validate_scene(scene)
    assert report["valid"] is False
    assert any(i["type"] == "door_outside_wall" for i in report["errors"])


def test_door_at_wall_boundary():
    # Door starts exactly at wall start (offset = 15, width = 30 -> [0, 30])
    scene = {
        "walls": [{"id": "w1", "start": [0.0, 0.0], "end": [100.0, 0.0], "thickness": 10.0}],
        "doors": [{"id": "d1", "wall_id": "w1", "offset": 15.0, "width": 30.0}]
    }
    report = validate_scene(scene)
    assert report["valid"] is True
    assert any(i["type"] == "boundary_door_position" and i["severity"] == "WARNING" for i in report["warnings"])


def test_door_wider_than_wall():
    scene = {
        "walls": [{"id": "w1", "start": [0.0, 0.0], "end": [20.0, 0.0], "thickness": 10.0}],
        "doors": [{"id": "d1", "wall_id": "w1", "offset": 10.0, "width": 35.0}]
    }
    report = validate_scene(scene)
    assert any(i["type"] == "door_exceeds_wall_length" for i in report["issues"])


def test_door_center_calculation():
    host_wall = {
        "geometry": {"start": [0.0, 0.0], "end": [100.0, 0.0], "length": 100.0}
    }
    opening = _compute_canonical_opening(host_wall, orig_center=(50.0, 0.0), width=20.0, height=2.1)
    assert math.isclose(opening["center"][0], 50.0, abs_tol=1e-2)
    assert math.isclose(opening["center"][1], 0.0, abs_tol=1e-2)
    assert math.isclose(opening["offset"], 50.0, abs_tol=1e-2)


def test_door_opening_interval_calculation():
    host_wall = {
        "geometry": {"start": [10.0, 0.0], "end": [110.0, 0.0], "length": 100.0}
    }
    # Center at x=40 (offset = 30 from wall start)
    opening = _compute_canonical_opening(host_wall, orig_center=(40.0, 0.0), width=20.0, height=2.1)
    assert math.isclose(opening["opening_start"], 20.0, abs_tol=1e-2)
    assert math.isclose(opening["opening_end"], 40.0, abs_tol=1e-2)
    assert opening["fits_within_wall"] is True


# ==============================================================================
# 3. WINDOW TESTS
# ==============================================================================

def test_window_valid():
    scene = {
        "walls": [{"id": "w1", "start": [0.0, 0.0], "end": [200.0, 0.0], "thickness": 10.0}],
        "windows": [{"id": "win1", "wall_id": "w1", "position": 0.5, "width": 40.0}]
    }
    report = validate_scene(scene)
    assert report["valid"] is True
    assert len(report["errors"]) == 0


def test_window_missing_wall_reference():
    scene = {
        "walls": [{"id": "w1", "start": [0.0, 0.0], "end": [100.0, 0.0], "thickness": 10.0}],
        "windows": [{"id": "win1", "wall_id": "w_unknown", "position": 0.5, "width": 30.0}]
    }
    report = validate_scene(scene)
    assert report["valid"] is False
    assert any(i["type"] == "missing_wall_reference" for i in report["errors"])


def test_window_outside_wall():
    scene = {
        "walls": [{"id": "w1", "start": [0.0, 0.0], "end": [40.0, 0.0], "thickness": 10.0}],
        "windows": [{"id": "win1", "wall_id": "w1", "offset": 35.0, "width": 30.0}]
    }
    report = validate_scene(scene)
    assert report["valid"] is False
    assert any(i["type"] == "window_outside_wall" for i in report["errors"])


def test_window_wider_than_wall():
    scene = {
        "walls": [{"id": "w1", "start": [0.0, 0.0], "end": [30.0, 0.0], "thickness": 10.0}],
        "windows": [{"id": "win1", "wall_id": "w1", "offset": 15.0, "width": 60.0}]
    }
    report = validate_scene(scene)
    assert any(i["type"] == "window_exceeds_wall_length" for i in report["issues"])


def test_window_center_calculation():
    host_wall = {
        "geometry": {"start": [0.0, 10.0], "end": [0.0, 110.0], "length": 100.0}
    }
    opening = _compute_canonical_opening(host_wall, orig_center=(0.0, 60.0), width=30.0, height=1.2, opening_type="window")
    assert math.isclose(opening["center"][0], 0.0, abs_tol=1e-2)
    assert math.isclose(opening["center"][1], 60.0, abs_tol=1e-2)
    assert math.isclose(opening["offset"], 50.0, abs_tol=1e-2)


def test_window_opening_interval_calculation():
    host_wall = {
        "geometry": {"start": [0.0, 0.0], "end": [0.0, 200.0], "length": 200.0}
    }
    opening = _compute_canonical_opening(host_wall, orig_center=(0.0, 100.0), width=40.0, height=1.2, opening_type="window")
    assert math.isclose(opening["opening_start"], 80.0, abs_tol=1e-2)
    assert math.isclose(opening["opening_end"], 120.0, abs_tol=1e-2)
    assert opening["fits_within_wall"] is True


# ==============================================================================
# 4. SCALE TESTS
# ==============================================================================

def test_scale_known():
    scene = {
        "walls": [{"id": "w1", "start": [0.0, 0.0], "end": [200.0, 0.0], "thickness": 20.0}],
        "doors": [{"id": "d1", "wall_id": "w1", "offset": 100.0, "width": 40.0}],
        "windows": [],
        "rooms": []
    }
    norm, rep = normalize_scene(scene, meters_per_pixel=0.02)
    assert norm["units"] == "meters"
    assert norm["coordinate_system"] == "world"
    assert norm["scale"]["meters_per_pixel"] == 0.02
    assert norm["scale"]["metric_available"] is True
    assert math.isclose(norm["walls"][0]["geometry"]["length"], 4.0, abs_tol=1e-3)
    assert math.isclose(norm["doors"][0]["width"], 0.8, abs_tol=1e-3)


def test_scale_unknown():
    scene = {
        "walls": [{"id": "w1", "start": [0.0, 0.0], "end": [200.0, 0.0], "thickness": 20.0}],
        "doors": [],
        "windows": [],
        "rooms": []
    }
    norm, rep = normalize_scene(scene, meters_per_pixel=None)
    assert norm["units"] == "pixels"
    assert norm["coordinate_system"] == "image"
    assert norm["scale"]["meters_per_pixel"] is None
    assert norm["scale"]["source"] == "unknown"
    assert norm["scale"]["confidence"] == 0.0
    assert norm["scale"]["metric_available"] is False


def test_scale_pixel_coordinates_preserved():
    scene = {
        "walls": [{"id": "w1", "start": [12.5, 45.8], "end": [212.5, 45.8], "thickness": 10.0}],
        "doors": [],
        "windows": [],
        "rooms": []
    }
    norm, _ = normalize_scene(scene, meters_per_pixel=None)
    w = norm["walls"][0]
    assert w["geometry"]["start"] == [12.5, 45.8]
    assert w["geometry"]["end"] == [212.5, 45.8]
    assert w["geometry"]["length"] == 200.0


def test_scale_metric_conversion():
    scale = estimate_scale_from_reference(pixel_length=100.0, real_length_meters=2.5)
    assert math.isclose(scale, 0.025, abs_tol=1e-5)


# ==============================================================================
# 5. ROOM TESTS
# ==============================================================================

def test_room_valid_polygon():
    scene = {
        "rooms": [{"id": "r1", "label": "Lounge", "polygon": [[0.0, 0.0], [100.0, 0.0], [100.0, 50.0], [0.0, 50.0]]}]
    }
    report = validate_scene(scene)
    assert report["valid"] is True
    rooms, _ = process_rooms(scene["rooms"])
    assert math.isclose(rooms[0]["geometry"]["area"], 5000.0, abs_tol=1.0)
    assert math.isclose(rooms[0]["geometry"]["perimeter"], 300.0, abs_tol=1.0)


def test_room_invalid_polygon():
    scene = {
        "rooms": [{"id": "r1", "polygon": [[0.0, 0.0], [100.0, 0.0]]}]  # only 2 points
    }
    report = validate_scene(scene)
    assert report["valid"] is False
    assert any(i["type"] == "insufficient_polygon_vertices" for i in report["errors"])


def test_room_self_intersecting_polygon():
    # Figure-8 polygon
    scene = {
        "rooms": [{"id": "r1", "polygon": [[0.0, 0.0], [100.0, 100.0], [0.0, 100.0], [100.0, 0.0]]}]
    }
    report = validate_scene(scene)
    assert report["valid"] is False
    assert any(i["type"] == "self_intersecting_room_polygon" for i in report["errors"])


def test_room_wall_consistency():
    # Rooms processed with normalize_scene maintain coordinate consistency
    scene = {
        "walls": [
            {"id": "w1", "start": [0.0, 0.0], "end": [100.0, 0.0], "thickness": 10.0},
            {"id": "w2", "start": [100.0, 0.0], "end": [100.0, 100.0], "thickness": 10.0},
            {"id": "w3", "start": [100.0, 100.0], "end": [0.0, 100.0], "thickness": 10.0},
            {"id": "w4", "start": [0.0, 100.0], "end": [0.0, 0.0], "thickness": 10.0}
        ],
        "rooms": [{"id": "r1", "polygon": [[0.0, 0.0], [100.0, 0.0], [100.0, 100.0], [0.0, 100.0]]}]
    }
    norm, report = normalize_scene(scene)
    assert report["valid"] is True
    assert norm["rooms"][0]["geometry"]["area"] == 10000.0


# ==============================================================================
# 6. PIPELINE INTEGRATION TEST ON ACTUAL scene.json
# ==============================================================================

def test_full_member2_pipeline_on_real_scene():
    scene_path = Path("scene.json")
    if not scene_path.exists():
        pytest.skip("scene.json not found in workspace")

    with open(scene_path, "r", encoding="utf-8") as f:
        raw_scene = json.load(f)

    normalized, report = normalize_scene(raw_scene)

    # 1. Scene must be valid
    assert report["valid"] is True
    assert report["status"] == "PASS"
    assert len(report["errors"]) == 0

    # 2. Wall consolidation
    assert len(normalized["walls"]) == 8  # 4 exterior + 4 interior partitions
    assert len(normalized["removed_walls"]) == 1  # w9 artifact
    assert normalized["removed_walls"][0]["id"] == "w9"

    # 3. Openings fit within continuous host walls
    for d in normalized["doors"]:
        assert d["geometry"]["fits_within_wall"] is True
    for w in normalized["windows"]:
        assert w["geometry"]["fits_within_wall"] is True

    # 4. Host wall reassignments resolved
    assert normalized["wall_reassignments"]["w11"] == "w2"
    d3 = next(d for d in normalized["doors"] if d["id"] == "d3")
    assert d3["wall_id"] == "w2"
    assert d3["source_wall_id"] == "w11"

    # 5. Rooms intact
    assert len(normalized["rooms"]) == 3
    for r in normalized["rooms"]:
        assert r["geometry"]["area"] > 0
