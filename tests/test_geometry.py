"""
Comprehensive automated tests for Member 2 geometry generation pipeline.
Covers TEST 1 through TEST 10 as specified in competition criteria, plus edge cases.
"""

import math
import pytest
import numpy as np
from shapely.geometry import Polygon

from src.schema import SceneSpecification, Wall, Door, Window, Room
from src.validator import SceneValidator
from src.scene_graph import SceneGraph
from src.exporter import SceneExporter
from src.geometry.room_builder import RoomMeshBuilder


# ==============================================================================
# TEST 1: Single rectangular room
# Expected: 4 walls, 1 floor, 1 ceiling
# ==============================================================================
def test_1_single_rectangular_room():
    spec = SceneSpecification(
        wall_height=3.0,
        walls=[
            Wall(id="w_south", start=(0.0, 0.0), end=(5.0, 0.0), thickness=0.15),
            Wall(id="w_east", start=(5.0, 0.0), end=(5.0, 4.0), thickness=0.15),
            Wall(id="w_north", start=(5.0, 4.0), end=(0.0, 4.0), thickness=0.15),
            Wall(id="w_west", start=(0.0, 4.0), end=(0.0, 0.0), thickness=0.15),
        ],
        rooms=[
            Room(id="room_main", name="Main Hall", polygon=[(0.0, 0.0), (5.0, 0.0), (5.0, 4.0), (0.0, 4.0)])
        ]
    )

    val_res = SceneValidator.validate_raw_json(spec.model_dump())
    assert val_res.is_valid, f"Validation errors: {val_res.errors}"

    sg = SceneGraph.from_specification(spec)

    wall_nodes = [n for n in sg.nodes.values() if n.node_type == "wall"]
    floor_nodes = [n for n in sg.nodes.values() if n.node_type == "floor"]
    ceiling_nodes = [n for n in sg.nodes.values() if n.node_type == "ceiling"]

    assert len(wall_nodes) == 4, f"Expected 4 walls, got {len(wall_nodes)}"
    assert len(floor_nodes) == 1, f"Expected 1 floor, got {len(floor_nodes)}"
    assert len(ceiling_nodes) == 1, f"Expected 1 ceiling, got {len(ceiling_nodes)}"

    # Check floor area
    assert math.isclose(floor_nodes[0].dimensions["area_m2"], 20.0, rel_tol=1e-4)


# ==============================================================================
# TEST 2: Room with one door
# Expected: Door opening correctly positioned, lintel present, aperture clear
# ==============================================================================
def test_2_room_with_one_door():
    spec = SceneSpecification(
        wall_height=3.0,
        walls=[
            Wall(id="w1", start=(0.0, 0.0), end=(6.0, 0.0), thickness=0.20)
        ],
        doors=[
            Door(id="d1", wall_id="w1", offset=2.0, width=1.0, height=2.1)
        ]
    )

    sg = SceneGraph.from_specification(spec, build_accessories=True)
    wall_node = sg.nodes["wall_w1"]
    assert wall_node.mesh is not None

    # The door aperture is from s=2.0 to s=3.0, between z=0.0 and z=2.1
    # Check that in the wall mesh, no vertex exists inside the interior of the opening
    # (i.e. x in (2.05, 2.95), y in (-0.09, 0.09), z in (0.05, 2.05))
    verts = wall_node.mesh.vertices
    in_opening = (
        (verts[:, 0] > 2.01) & (verts[:, 0] < 2.99) &
        (verts[:, 2] > 0.01) & (verts[:, 2] < 2.09)
    )
    assert not np.any(in_opening), "Found wall vertices inside the door opening volume!"

    # Above z=2.1 (the lintel), vertices must exist
    in_lintel = (
        (verts[:, 0] >= 2.0) & (verts[:, 0] <= 3.0) &
        (verts[:, 2] >= 2.1) & (verts[:, 2] <= 3.0)
    )
    assert np.any(in_lintel), "Missing lintel geometry above the door!"

    # Door accessory nodes exist
    assert "door_frame_d1" in sg.nodes
    assert "door_leaf_d1" in sg.nodes


# ==============================================================================
# TEST 3: Room with one window
# Expected: Window opening correctly positioned, sill and lintel present
# ==============================================================================
def test_3_room_with_one_window():
    spec = SceneSpecification(
        wall_height=3.0,
        walls=[
            Wall(id="w1", start=(0.0, 0.0), end=(6.0, 0.0), thickness=0.20)
        ],
        windows=[
            Window(id="win1", wall_id="w1", offset=1.5, width=1.5, height=1.2, sill_height=0.9)
        ]
    )

    sg = SceneGraph.from_specification(spec, build_accessories=True)
    wall_node = sg.nodes["wall_w1"]
    verts = wall_node.mesh.vertices

    # Sill exists (z in [0.0, 0.9])
    in_sill = (verts[:, 0] >= 1.5) & (verts[:, 0] <= 3.0) & (verts[:, 2] <= 0.9)
    assert np.any(in_sill), "Missing window sill geometry below sill height!"

    # Lintel exists (z in [2.1, 3.0])
    in_lintel = (verts[:, 0] >= 1.5) & (verts[:, 0] <= 3.0) & (verts[:, 2] >= 2.1)
    assert np.any(in_lintel), "Missing window lintel geometry above window!"

    # Aperture is clear (s in (1.55, 2.95), z in (0.95, 2.05))
    in_aperture = (
        (verts[:, 0] > 1.51) & (verts[:, 0] < 2.99) &
        (verts[:, 2] > 0.91) & (verts[:, 2] < 2.09)
    )
    assert not np.any(in_aperture), "Found wall vertices inside the window aperture volume!"

    assert "window_frame_win1" in sg.nodes
    assert "window_glass_win1" in sg.nodes


# ==============================================================================
# TEST 4: Room with door + window on same wall
# ==============================================================================
def test_4_room_with_door_and_window():
    spec = SceneSpecification(
        wall_height=3.0,
        walls=[
            Wall(id="w_front", start=(0.0, 0.0), end=(7.0, 0.0), thickness=0.20)
        ],
        doors=[
            Door(id="d1", wall_id="w_front", offset=0.5, width=0.9, height=2.1)
        ],
        windows=[
            Window(id="w1", wall_id="w_front", offset=3.0, width=2.0, height=1.2, sill_height=0.9)
        ]
    )

    val_res = SceneValidator.validate_raw_json(spec.model_dump())
    assert val_res.is_valid

    sg = SceneGraph.from_specification(spec)
    assert "wall_w_front" in sg.nodes
    assert "door_frame_d1" in sg.nodes
    assert "window_frame_w1" in sg.nodes


# ==============================================================================
# TEST 5: Multiple rooms
# ==============================================================================
def test_5_multiple_rooms():
    spec = SceneSpecification(
        wall_height=2.8,
        rooms=[
            Room(id="room_a", name="Living Room", polygon=[(0.0, 0.0), (4.0, 0.0), (4.0, 4.0), (0.0, 4.0)]),
            Room(id="room_b", name="Bedroom", polygon=[(4.0, 0.0), (8.0, 0.0), (8.0, 4.0), (4.0, 4.0)]),
        ]
    )

    val_res = SceneValidator.validate_raw_json(spec.model_dump())
    assert val_res.is_valid
    assert val_res.report["total_floor_area_m2"] == 32.0

    sg = SceneGraph.from_specification(spec)
    assert "floor_room_a" in sg.nodes
    assert "floor_room_b" in sg.nodes
    assert "ceiling_room_a" in sg.nodes
    assert "ceiling_room_b" in sg.nodes


# ==============================================================================
# TEST 6: Shared wall between rooms
# ==============================================================================
def test_6_shared_wall_between_rooms():
    spec = SceneSpecification(
        wall_height=2.8,
        walls=[
            Wall(id="shared_wall", start=(4.0, 0.0), end=(4.0, 4.0), thickness=0.15)
        ],
        rooms=[
            Room(id="room_a", polygon=[(0.0, 0.0), (4.0, 0.0), (4.0, 4.0), (0.0, 4.0)]),
            Room(id="room_b", polygon=[(4.0, 0.0), (8.0, 0.0), (8.0, 4.0), (4.0, 4.0)])
        ]
    )

    shared = RoomMeshBuilder.detect_shared_walls(spec.walls, spec.rooms)
    assert "shared_wall" in shared
    assert set(shared["shared_wall"]) == {"room_a", "room_b"}

    sg = SceneGraph.from_specification(spec)
    wall_node = sg.nodes["wall_shared_wall"]
    assert wall_node.metadata["is_shared_wall"] is True
    assert set(wall_node.relationships["bordering_rooms"]) == {"room_a", "room_b"}


# ==============================================================================
# TEST 7: Different wall orientations (0°, 90°, 45°, arbitrary)
# ==============================================================================
def test_7_different_wall_orientations():
    walls = [
        Wall(id="horiz", start=(0.0, 0.0), end=(5.0, 0.0), thickness=0.15),
        Wall(id="vert", start=(0.0, 0.0), end=(0.0, 5.0), thickness=0.15),
        Wall(id="diag_45", start=(0.0, 0.0), end=(4.0, 4.0), thickness=0.15),
        Wall(id="arbitrary", start=(1.0, 2.0), end=(5.0, 7.0), thickness=0.15),
    ]
    spec = SceneSpecification(wall_height=3.0, walls=walls)

    sg = SceneGraph.from_specification(spec)
    for w in walls:
        node = sg.nodes[f"wall_{w.id}"]
        assert node.mesh is not None
        assert len(node.mesh.faces) > 0
        assert math.isclose(node.dimensions["length_m"], w.length, rel_tol=1e-4)


# ==============================================================================
# TEST 8: Non-square (L-shaped) room
# ==============================================================================
def test_8_non_square_l_shaped_room():
    # L-shaped polygon: 6x3 + 3x3 = 27 m²
    l_poly = [(0.0, 0.0), (6.0, 0.0), (6.0, 3.0), (3.0, 3.0), (3.0, 6.0), (0.0, 6.0)]
    spec = SceneSpecification(
        wall_height=3.0,
        rooms=[
            Room(id="room_l", name="L-Shaped Suite", polygon=l_poly)
        ]
    )

    val_res = SceneValidator.validate_raw_json(spec.model_dump())
    assert val_res.is_valid
    assert math.isclose(val_res.report["total_floor_area_m2"], 27.0, rel_tol=1e-4)

    sg = SceneGraph.from_specification(spec)
    floor = sg.nodes["floor_room_l"]
    assert math.isclose(floor.dimensions["area_m2"], 27.0, rel_tol=1e-4)


# ==============================================================================
# TEST 9: Invalid scene.json handling (strict rejection with clear errors)
# ==============================================================================
def test_9_invalid_scene_json():
    # 9a: Nonexistent wall referenced by door
    data_missing_wall = {
        "walls": [{"id": "w1", "start": [0, 0], "end": [5, 0], "thickness": 0.2}],
        "doors": [{"id": "d1", "wall_id": "wall_nonexistent", "offset": 1.0, "width": 0.9, "height": 2.1}]
    }
    res_a = SceneValidator.validate_raw_json(data_missing_wall)
    assert not res_a.is_valid
    assert any("references wall 'wall_nonexistent', but 'wall_nonexistent' does not exist" in e for e in res_a.errors)

    # 9b: Door extends outside wall
    data_overflow_door = {
        "walls": [{"id": "w1", "start": [0, 0], "end": [2.0, 0], "thickness": 0.2}],
        "doors": [{"id": "d1", "wall_id": "w1", "offset": 1.5, "width": 1.0, "height": 2.1}]
    }
    res_b = SceneValidator.validate_raw_json(data_overflow_door)
    assert not res_b.is_valid
    assert any("exceeds wall 'w1' length" in e for e in res_b.errors)

    # 9c: Zero-length wall
    data_zero_wall = {
        "walls": [{"id": "w_zero", "start": [1.0, 1.0], "end": [1.0, 1.0], "thickness": 0.2}]
    }
    res_c = SceneValidator.validate_raw_json(data_zero_wall)
    assert not res_c.is_valid

    # 9d: Overlapping openings
    data_overlap = {
        "walls": [{"id": "w1", "start": [0, 0], "end": [6.0, 0], "thickness": 0.2}],
        "doors": [{"id": "d1", "wall_id": "w1", "offset": 1.0, "width": 1.5, "height": 2.1}],
        "windows": [{"id": "win1", "wall_id": "w1", "offset": 1.8, "width": 1.5, "height": 1.2, "sill_height": 0.9}]
    }
    res_d = SceneValidator.validate_raw_json(data_overlap)
    assert not res_d.is_valid
    assert any("overlapping openings" in e for e in res_d.errors)


# ==============================================================================
# TEST 10: Dimension preservation
# Input: width = 5.2m, length = 4.8m, height = 3.0m
# Generated model preserves dimensions within very small numerical tolerance
# ==============================================================================
def test_10_dimension_preservation():
    w_len = 5.2
    w_th = 0.15
    w_h = 3.0
    r_w = 5.2
    r_d = 4.8

    spec = SceneSpecification(
        wall_height=w_h,
        walls=[
            Wall(id="w_precise", start=(0.0, 0.0), end=(w_len, 0.0), thickness=w_th, height=w_h)
        ],
        rooms=[
            Room(id="room_precise", polygon=[(0.0, 0.0), (r_w, 0.0), (r_w, r_d), (0.0, r_d)])
        ]
    )

    sg = SceneGraph.from_specification(spec)
    w_node = sg.nodes["wall_w_precise"]

    # Wall length dimension
    assert math.isclose(w_node.dimensions["length_m"], w_len, abs_tol=1e-5)
    # Wall thickness dimension
    assert math.isclose(w_node.dimensions["thickness_m"], w_th, abs_tol=1e-5)
    # Wall height dimension
    assert math.isclose(w_node.dimensions["height_m"], w_h, abs_tol=1e-5)

    # Wall mesh bounding box checks
    bbox = w_node.bounding_box_3d
    # Z height span: bbox[5] - bbox[2] == 3.0
    assert math.isclose(bbox[5] - bbox[2], w_h, abs_tol=1e-4)
    # X length span: bbox[3] - bbox[0] == 5.2
    assert math.isclose(bbox[3] - bbox[0], w_len, abs_tol=1e-4)
    # Y thickness span: bbox[4] - bbox[1] == 0.15
    assert math.isclose(bbox[4] - bbox[1], w_th, abs_tol=1e-4)

    # Room floor area
    f_node = sg.nodes["floor_room_precise"]
    expected_area = r_w * r_d
    assert math.isclose(f_node.dimensions["area_m2"], expected_area, abs_tol=1e-4)


# ==============================================================================
# TEST 11: Export formats (GLB, OBJ, PLY)
# ==============================================================================
def test_11_export_formats(tmp_path):
    spec = SceneSpecification(
        walls=[Wall(id="w1", start=(0.0, 0.0), end=(4.0, 0.0), thickness=0.2)],
        rooms=[Room(id="r1", polygon=[(0.0, 0.0), (4.0, 0.0), (4.0, 3.0), (0.0, 3.0)])]
    )
    sg = SceneGraph.from_specification(spec)

    glb_file = SceneExporter.export(sg, tmp_path / "model.glb", "glb")
    obj_file = SceneExporter.export(sg, tmp_path / "model.obj", "obj")
    ply_file = SceneExporter.export(sg, tmp_path / "model.ply", "ply")

    assert glb_file.exists() and glb_file.stat().st_size > 0
    assert obj_file.exists() and obj_file.stat().st_size > 0
    assert ply_file.exists() and ply_file.stat().st_size > 0


# ==============================================================================
# TEST 12: Security & Untrusted Input (Reject NaN, Inf, pathological values)
# ==============================================================================
def test_12_security_untrusted_input():
    # NaN check
    data_nan = {
        "walls": [{"id": "w1", "start": [float("nan"), 0], "end": [5, 0], "thickness": 0.2}]
    }
    res_nan = SceneValidator.validate_raw_json(data_nan)
    assert not res_nan.is_valid

    # Extreme coordinate check
    data_inf = {
        "walls": [{"id": "w1", "start": [0, 0], "end": [9999999.0, 0], "thickness": 0.2}]
    }
    res_inf = SceneValidator.validate_raw_json(data_inf)
    assert not res_inf.is_valid
