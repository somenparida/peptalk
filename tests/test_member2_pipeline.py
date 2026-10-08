"""
Member 2 Automated Unit Tests.
Covers all 12 required test cases from the Member 2 Specification:
1. Valid wall
2. Invalid wall
3. Missing wall reference
4. Invalid door
5. Invalid window
6. Duplicate wall
7. Short wall
8. Nearly touching walls
9. Valid room polygon
10. Invalid room polygon
11. Known scale conversion
12. Unknown scale behavior
"""

import math
import pytest
from geometry.validator import validate_scene
from geometry.topology import clean_topology, snap_endpoints
from geometry.scale import convert_to_metric, estimate_scale_from_reference
from geometry.normalize import normalize_scene


# 1. Valid wall
def test_1_valid_wall():
    scene = {
        "walls": [
            {"id": "w1", "start": [0.0, 0.0], "end": [100.0, 0.0], "thickness": 10.0}
        ]
    }
    res = validate_scene(scene)
    assert res["valid"] is True
    assert len([i for i in res["issues"] if i["severity"] == "error"]) == 0


# 2. Invalid wall (missing field, negative thickness, non-numeric coords)
def test_2_invalid_wall():
    scene_missing = {
        "walls": [{"id": "w1", "start": [0, 0], "end": [100, 0]}]  # missing thickness
    }
    res_missing = validate_scene(scene_missing)
    assert any(i["type"] == "missing_wall_field" for i in res_missing["issues"])

    scene_thickness = {
        "walls": [{"id": "w1", "start": [0, 0], "end": [100, 0], "thickness": -5.0}]
    }
    res_th = validate_scene(scene_thickness)
    assert res_th["valid"] is False
    assert any(i["type"] == "invalid_thickness" for i in res_th["issues"])

    scene_coords = {
        "walls": [{"id": "w1", "start": ["invalid", 0], "end": [100, 0], "thickness": 10.0}]
    }
    res_c = validate_scene(scene_coords)
    assert res_c["valid"] is False
    assert any(i["type"] == "invalid_coordinates" for i in res_c["issues"])


# 3. Missing wall reference (door or window pointing to non-existent wall)
def test_3_missing_wall_reference():
    scene = {
        "walls": [{"id": "w1", "start": [0, 0], "end": [100, 0], "thickness": 10}],
        "doors": [{"id": "d1", "wall_id": "w_nonexistent", "position": 0.5, "width": 20}],
        "windows": [{"id": "win1", "wall_id": "w_missing", "position": 0.5, "width": 20}]
    }
    res = validate_scene(scene)
    assert res["valid"] is False
    missing_refs = [i for i in res["issues"] if i["type"] == "missing_wall_reference"]
    assert len(missing_refs) == 2


# 4. Invalid door (negative width, out-of-bounds position)
def test_4_invalid_door():
    scene = {
        "walls": [{"id": "w1", "start": [0, 0], "end": [100, 0], "thickness": 10}],
        "doors": [
            {"id": "d_bad_w", "wall_id": "w1", "position": 0.5, "width": -10.0},
            {"id": "d_bad_pos", "wall_id": "w1", "position": 1.5, "width": 20.0}
        ]
    }
    res = validate_scene(scene)
    assert res["valid"] is False
    assert any(i["type"] == "invalid_door_width" for i in res["issues"])
    assert any(i["type"] == "invalid_door_position" for i in res["issues"])


# 5. Invalid window (negative width, non-numeric position)
def test_5_invalid_window():
    scene = {
        "walls": [{"id": "w1", "start": [0, 0], "end": [100, 0], "thickness": 10}],
        "windows": [
            {"id": "win_neg", "wall_id": "w1", "position": 0.5, "width": -15.0},
            {"id": "win_nan", "wall_id": "w1", "position": "bad_pos", "width": 20.0}
        ]
    }
    res = validate_scene(scene)
    assert res["valid"] is False
    assert any(i["type"] == "invalid_window_width" for i in res["issues"])
    assert any(i["type"] == "invalid_window_position" for i in res["issues"])


# 6. Duplicate wall
def test_6_duplicate_wall():
    scene = {
        "walls": [
            {"id": "w1", "start": [0.0, 0.0], "end": [100.0, 0.0], "thickness": 10.0},
            {"id": "w2", "start": [0.0, 0.0], "end": [100.0, 0.0], "thickness": 10.0}
        ]
    }
    res = validate_scene(scene)
    assert any(i["type"] == "duplicate_wall_geometry" for i in res["issues"])


# 7. Short wall (length < MIN_WALL_LENGTH)
def test_7_short_wall():
    scene = {
        "walls": [
            {"id": "w_short", "start": [72.0, 150.0], "end": [84.0, 150.0], "thickness": 4.0}  # length = 12px
        ]
    }
    res = validate_scene(scene)
    short_issues = [i for i in res["issues"] if i["type"] == "short_wall"]
    assert len(short_issues) == 1
    assert short_issues[0]["element_id"] == "w_short"
    assert short_issues[0]["severity"] == "warning"


# 8. Nearly touching walls (snapping)
def test_8_nearly_touching_walls():
    scene = {
        "walls": [
            {"id": "w1", "start": [0.0, 0.0], "end": [100.0, 0.0], "thickness": 10.0},
            {"id": "w2", "start": [105.0, 0.0], "end": [105.0, 50.0], "thickness": 10.0}  # gap = 5.0px
        ]
    }
    cleaned = clean_topology(scene, snap_tol=10.0)
    w1_end = cleaned["walls"][0]["geometry"]["end"]
    w2_start = cleaned["walls"][1]["geometry"]["start"]

    # Snapped to cluster centroid (102.5, 0.0)
    assert math.isclose(w1_end[0], w2_start[0], abs_tol=1e-3)
    assert math.isclose(w1_end[1], w2_start[1], abs_tol=1e-3)
    assert len(cleaned["topology_operations"]) > 0


# 9. Valid room polygon
def test_9_valid_room_polygon():
    scene = {
        "rooms": [
            {"id": "r1", "label": "Living Room", "polygon": [[0.0, 0.0], [100.0, 0.0], [100.0, 80.0], [0.0, 80.0]]}
        ]
    }
    res = validate_scene(scene)
    assert res["valid"] is True
    normalized, _ = normalize_scene(scene)
    r_geom = normalized["rooms"][0]["geometry"]
    assert math.isclose(r_geom["area"], 8000.0, abs_tol=1.0)
    assert math.isclose(r_geom["perimeter"], 360.0, abs_tol=1.0)


# 10. Invalid room polygon (< 3 vertices, non-numeric)
def test_10_invalid_room_polygon():
    scene_few = {
        "rooms": [{"id": "r1", "polygon": [[0, 0], [100, 0]]}]  # only 2 points
    }
    res_few = validate_scene(scene_few)
    assert res_few["valid"] is False
    assert any(i["type"] == "insufficient_polygon_vertices" for i in res_few["issues"])

    scene_bad_pts = {
        "rooms": [{"id": "r1", "polygon": [[0, 0], ["bad", 0], [100, 100]]}]
    }
    res_bad = validate_scene(scene_bad_pts)
    assert res_bad["valid"] is False
    assert any(i["type"] == "invalid_room_coordinate" for i in res_bad["issues"])


# 11. Known scale conversion
def test_11_known_scale_conversion():
    scene = {
        "walls": [{"id": "w1", "start": [0.0, 0.0], "end": [200.0, 0.0], "thickness": 20.0}],
        "doors": [{"id": "d1", "wall_id": "w1", "position": 0.5, "width": 40.0}],
        "windows": [],
        "rooms": [{"id": "r1", "polygon": [[0.0, 0.0], [200.0, 0.0], [200.0, 100.0], [0.0, 100.0]]}]
    }
    # 1 pixel = 0.02 meters (200px = 4.0 meters)
    normalized, report = normalize_scene(scene, meters_per_pixel=0.02)
    assert normalized["units"] == "meters"
    assert normalized["coordinate_system"] == "world"
    assert normalized["scale"]["meters_per_pixel"] == 0.02
    assert normalized["scale"]["metric_available"] is True

    w_geom = normalized["walls"][0]["geometry"]
    assert math.isclose(w_geom["length"], 4.0, abs_tol=1e-3)
    assert math.isclose(w_geom["thickness"], 0.4, abs_tol=1e-3)

    d_geom = normalized["doors"][0]["geometry"]
    assert math.isclose(d_geom["width"], 0.8, abs_tol=1e-3)

    r_geom = normalized["rooms"][0]["geometry"]
    assert math.isclose(r_geom["area"], 8.0, abs_tol=1e-3)  # (4m * 2m = 8m²)


# 12. Unknown scale behavior (preserves pixel units, no fabrication)
def test_12_unknown_scale_behavior():
    scene = {
        "walls": [{"id": "w1", "start": [0.0, 0.0], "end": [200.0, 0.0], "thickness": 20.0}],
        "doors": [],
        "windows": [],
        "rooms": []
    }
    normalized, report = normalize_scene(scene, meters_per_pixel=None)
    assert normalized["units"] == "pixels"
    assert normalized["coordinate_system"] == "image"
    assert normalized["scale"]["meters_per_pixel"] is None
    assert normalized["scale"]["source"] == "unknown"
    assert normalized["scale"]["confidence"] == 0.0
    assert normalized["scale"]["metric_available"] is False
    assert normalized["walls"][0]["geometry"]["length"] == 200.0
