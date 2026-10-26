import numpy as np
"""Unit tests for Stage 3: Procedural 3D Mesh Reconstruction Engine."""

import pytest
import trimesh

from src.builder.mesh_utils import create_transformed_box
from src.builder.opening_builder import OpeningMeshBuilder
from src.builder.scene_builder import ArchitecturalSceneBuilder
from src.builder.slab_builder import SlabMeshBuilder, extrude_polygon_to_slab
from src.builder.wall_builder import WallMeshBuilder
from src.config import CONFIG
from src.models import (
    FloorPlan,
    OpeningInterval,
    OpeningType,
    Point2D,
    RoomPolygon,
    WallEdge,
)


def test_create_transformed_box_watertightness():
    box = create_transformed_box(
        s0=0.0,
        s1=4.0,
        t0=-0.1,
        t1=0.1,
        z0=0.0,
        z1=2.8,
        start=Point2D(0.0, 0.0),
        direction=(1.0, 0.0),
        normal=(0.0, 1.0),
        color=CONFIG.COLOR_WALL,
    )

    assert not box.is_empty
    assert len(box.vertices) == 8
    assert len(box.faces) == 12
    # Verify Euler characteristic for closed sphere topology V - E + F = 2
    # For a box with 8 verts, 12 triangles (18 edges): 8 - 18 + 12 = 2!
    assert box.is_watertight
    assert box.volume == pytest.approx(4.0 * 0.2 * 2.8, abs=1e-3)


def test_wall_mesh_builder_with_openings():
    builder = WallMeshBuilder()

    wall = WallEdge(
        id="W_TEST",
        start=Point2D(0.0, 0.0),
        end=Point2D(8.0, 0.0),
        thickness=0.20,
        height=2.80,
    )
    # Add Door [1.0, 2.0] and Window [4.0, 5.5]
    wall.add_opening(OpeningInterval(
        start_dist=1.0, end_dist=2.0, opening_type=OpeningType.DOOR, height=2.1, sill_height=0.0
    ))
    wall.add_opening(OpeningInterval(
        start_dist=4.0, end_dist=5.5, opening_type=OpeningType.WINDOW, height=1.2, sill_height=0.9
    ))

    w_mesh, l_mesh = builder.build_wall_mesh(wall)

    assert not w_mesh.is_empty
    assert not l_mesh.is_empty
    assert w_mesh.is_watertight
    assert l_mesh.is_watertight


def test_opening_mesh_builder():
    builder = OpeningMeshBuilder()

    wall = WallEdge(id="W1", start=Point2D(0.0, 0.0), end=Point2D(6.0, 0.0))
    door = OpeningInterval(start_dist=1.0, end_dist=2.0, opening_type=OpeningType.DOOR)
    win = OpeningInterval(start_dist=3.0, end_dist=4.5, opening_type=OpeningType.WINDOW)

    door_dict = builder.build_door_mesh(wall, door)
    assert not door_dict["door_frame"].is_empty
    assert not door_dict["door_leaf"].is_empty

    win_dict = builder.build_window_mesh(wall, win)
    assert not win_dict["window_frame"].is_empty
    assert not win_dict["window_glass"].is_empty
    assert not win_dict["window_sill"].is_empty


def test_slab_mesh_builder():
    builder = SlabMeshBuilder()

    room = RoomPolygon(
        id="R1",
        name="Living",
        points=[Point2D(0.0, 0.0), Point2D(5.0, 0.0), Point2D(5.0, 4.0), Point2D(0.0, 4.0)],
    )

    floors = builder.build_room_floors([room])
    assert not floors.is_empty
    assert floors.is_watertight
    # Slab thickness is 0.15m, area is 20m² -> volume is 3.0 m³
    assert floors.volume == pytest.approx(5.0 * 4.0 * CONFIG.FLOOR_SLAB_THICKNESS, abs=0.1)

    ceilings = builder.build_ceilings([room])
    assert not ceilings.is_empty
    assert ceilings.is_watertight


def test_scene_builder():
    builder = ArchitecturalSceneBuilder()

    w1 = WallEdge(id="W1", start=Point2D(0.0, 0.0), end=Point2D(4.0, 0.0))
    w2 = WallEdge(id="W2", start=Point2D(4.0, 0.0), end=Point2D(4.0, 4.0))
    w3 = WallEdge(id="W3", start=Point2D(4.0, 4.0), end=Point2D(0.0, 4.0))
    w4 = WallEdge(id="W4", start=Point2D(0.0, 4.0), end=Point2D(0.0, 0.0))

    w1.add_opening(OpeningInterval(start_dist=1.0, end_dist=2.0, opening_type=OpeningType.DOOR))

    room = RoomPolygon(
        id="R1",
        name="Studio",
        points=[Point2D(0.0, 0.0), Point2D(4.0, 0.0), Point2D(4.0, 4.0), Point2D(0.0, 4.0)],
    )

    plan = FloorPlan(walls=[w1, w2, w3, w4], rooms=[room])
    scene = builder.build_scene(plan)

    assert isinstance(scene, trimesh.Scene)
    assert "Walls" in scene.geometry
    assert "Floors" in scene.geometry
    assert "Ceilings" in scene.geometry
    assert scene.metadata["total_floor_area_sq_m"] == pytest.approx(16.0)


def test_window_sill_wall_no_overlap():
    """Verify that masonry wall beneath window terminates exactly at stone sill underside."""
    wall_builder = WallMeshBuilder()
    opening_builder = OpeningMeshBuilder()

    wall = WallEdge(
        id="W_SILL_TEST",
        start=Point2D(0.0, 0.0),
        end=Point2D(5.0, 0.0),
        thickness=0.20,
        height=2.80,
    )
    win = OpeningInterval(
        start_dist=1.5,
        end_dist=3.5,
        opening_type=OpeningType.WINDOW,
        height=1.20,
        sill_height=0.90,
    )
    wall.add_opening(win)

    w_mesh, l_mesh = wall_builder.build_wall_mesh(wall)
    win_dict = opening_builder.build_window_mesh(wall, win)
    sill_mesh = win_dict["window_sill"]

    assert not w_mesh.is_empty
    assert not sill_mesh.is_empty
    assert w_mesh.is_watertight
    assert sill_mesh.is_watertight

    # Sill mesh elevation
    sill_z_min = sill_mesh.bounds[0, 2]
    sill_z_max = sill_mesh.bounds[1, 2]
    assert sill_z_max == pytest.approx(0.90, abs=1e-4)
    assert sill_z_min == pytest.approx(0.90 - CONFIG.WINDOW_SILL_THICKNESS, abs=1e-4)

    # Wall vertices for the sub-window sill masonry must terminate at sill_z_min without overlap
    sill_wall_verts = w_mesh.vertices[(w_mesh.vertices[:, 2] > 0.0) & (w_mesh.vertices[:, 2] < 2.0)]
    assert len(sill_wall_verts) > 0
    sill_wall_z_max = np.max(sill_wall_verts[:, 2])
    assert sill_wall_z_max <= sill_z_min + 1e-4
    assert sill_wall_z_max == pytest.approx(sill_z_min, abs=1e-4)


def test_door_hardware_spindle_connected_no_air_gap():
    """Verify that door hardware has connecting spindles without air gaps between backplate and lever."""
    opening_builder = OpeningMeshBuilder()
    wall = WallEdge(id="W_DOOR", start=Point2D(0.0, 0.0), end=Point2D(4.0, 0.0))
    door = OpeningInterval(start_dist=1.0, end_dist=2.0, opening_type=OpeningType.DOOR)

    door_dict = opening_builder.build_door_mesh(wall, door)
    hw_mesh = door_dict["door_hardware"]

    assert not hw_mesh.is_empty
    assert hw_mesh.is_watertight

    half_leaf_t = 0.022
    plate_t = 0.008
    lever_offset = 0.040
    lever_t = 0.015

    # Check that in t (along Y axis since wall runs along X: start (0,0) to end (4,0), normal is (0,1)):
    # Front side hardware must span continuously from half_leaf_t to half_leaf_t + lever_offset + lever_t
    front_verts_y = hw_mesh.vertices[hw_mesh.vertices[:, 1] > 0, 1]
    assert np.min(front_verts_y) == pytest.approx(half_leaf_t, abs=1e-4)
    assert np.max(front_verts_y) == pytest.approx(half_leaf_t + lever_offset + lever_t, abs=1e-4)

    # Back side hardware must span continuously from -(half_leaf_t + lever_offset + lever_t) to -half_leaf_t
    back_verts_y = hw_mesh.vertices[hw_mesh.vertices[:, 1] < 0, 1]
    assert np.max(back_verts_y) == pytest.approx(-half_leaf_t, abs=1e-4)
    assert np.min(back_verts_y) == pytest.approx(-(half_leaf_t + lever_offset + lever_t), abs=1e-4)


def test_door_hinge_metadata_latch_positioning():
    """Verify that hinge metadata ('start' vs 'end') controls latch side positioning."""
    opening_builder = OpeningMeshBuilder()
    wall = WallEdge(id="W_HINGE", start=Point2D(0.0, 0.0), end=Point2D(4.0, 0.0))

    # Door 1: Hinge at start -> Latch at s1 end
    door_start = OpeningInterval(
        start_dist=1.0, end_dist=2.0, opening_type=OpeningType.DOOR, metadata={"hinge": "start"}
    )
    dict_start = opening_builder.build_door_mesh(wall, door_start)
    hw_start = dict_start["door_hardware"]
    centroid_x_start = np.mean(hw_start.vertices[:, 0])

    # Door 2: Hinge at end -> Latch at s0 start
    door_end = OpeningInterval(
        start_dist=1.0, end_dist=2.0, opening_type=OpeningType.DOOR, metadata={"hinge": "end"}
    )
    dict_end = opening_builder.build_door_mesh(wall, door_end)
    hw_end = dict_end["door_hardware"]
    centroid_x_end = np.mean(hw_end.vertices[:, 0])

    # Hardware for hinge="end" must be placed closer to s0 (start_dist=1.0)
    # Hardware for hinge="start" must be placed closer to s1 (end_dist=2.0)
    assert centroid_x_end < centroid_x_start
    assert centroid_x_end < 1.4
    assert centroid_x_start > 1.6

    # Test fallback on invalid / missing metadata: defaults to "start"
    door_default = OpeningInterval(
        start_dist=1.0, end_dist=2.0, opening_type=OpeningType.DOOR, metadata={"hinge": "invalid_value"}
    )
    dict_default = opening_builder.build_door_mesh(wall, door_default)
    hw_default = dict_default["door_hardware"]
    assert np.mean(hw_default.vertices[:, 0]) == pytest.approx(centroid_x_start, abs=1e-4)


def test_door_frame_non_overlapping_corners():
    """Verify that door frame header and jambs join flush with zero overlapping corner volume."""
    opening_builder = OpeningMeshBuilder()
    wall = WallEdge(id="W_FRAME", start=Point2D(0.0, 0.0), end=Point2D(4.0, 0.0))
    door = OpeningInterval(start_dist=1.0, end_dist=2.0, opening_type=OpeningType.DOOR, height=2.10)

    door_dict = opening_builder.build_door_mesh(wall, door)
    frame_mesh = door_dict["door_frame"]

    assert not frame_mesh.is_empty
    assert frame_mesh.is_watertight

    frame_t = CONFIG.DOOR_FRAME_THICKNESS  # 0.05
    frame_d = CONFIG.DOOR_FRAME_DEPTH      # 0.22
    opening_w = 1.0
    opening_h = 2.10

    # Two jambs: 2 * (frame_t * frame_d * opening_h)
    jambs_vol = 2.0 * (frame_t * frame_d * opening_h)
    # Header fitting flush between jambs: (opening_w - 2 * frame_t) * frame_d * frame_t
    header_vol = (opening_w - 2.0 * frame_t) * frame_d * frame_t
    expected_vol = jambs_vol + header_vol

    assert frame_mesh.volume == pytest.approx(expected_vol, abs=1e-4)
