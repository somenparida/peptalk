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
