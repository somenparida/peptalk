"""Unit tests for Stage 2: Topological Graph & Geometry Cleanup Engine."""

import math
import pytest

from src.config import CONFIG
from src.geometry.binding import OpeningBinder, RawOpening
from src.geometry.graph import WallGraph
from src.geometry.merging import CollinearWallMerger
from src.geometry.rooms import RoomTopologyEngine
from src.geometry.snapping import SnappingEngine
from src.geometry.validator import FloorPlanValidator
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


def test_point2d_operations():
    p1 = Point2D(0.0, 0.0)
    p2 = Point2D(3.0, 4.0)

    assert p1.distance_to(p2) == pytest.approx(5.0)
    assert p1.vector_to(p2) == (3.0, 4.0)
    assert (p1 + p2) == Point2D(3.0, 4.0)
    assert (p2 - p1) == Point2D(3.0, 4.0)
    assert (p2 * 2.0) == Point2D(6.0, 8.0)


def test_wall_edge_projection_and_openings():
    # Wall from (0, 0) to (10, 0)
    wall = WallEdge(id="W1", start=Point2D(0.0, 0.0), end=Point2D(10.0, 0.0))
    assert wall.length == pytest.approx(10.0)
    assert wall.direction == pytest.approx((1.0, 0.0))
    assert wall.normal == pytest.approx((0.0, 1.0))

    # Test point projection
    t, d_perp = wall.project_point(Point2D(4.0, 0.5))
    assert t == pytest.approx(4.0)
    assert d_perp == pytest.approx(0.5)

    # Add door from 2.0 to 3.0
    door = OpeningInterval(start_dist=2.0, end_dist=3.0, opening_type=OpeningType.DOOR, id="D1")
    assert wall.add_opening(door) is True

    # Add window from 6.0 to 8.0
    win = OpeningInterval(start_dist=6.0, end_dist=8.0, opening_type=OpeningType.WINDOW, id="W1_WIN")
    assert wall.add_opening(win) is True

    # Attempt overlapping opening (should fail)
    overlap_op = OpeningInterval(start_dist=2.5, end_dist=3.5, opening_type=OpeningType.DOOR)
    assert wall.add_opening(overlap_op) is False

    # Check solid intervals
    solids = wall.get_solid_intervals()
    assert len(solids) == 3
    assert solids[0] == pytest.approx((0.0, 2.0))
    assert solids[1] == pytest.approx((3.0, 6.0))
    assert solids[2] == pytest.approx((8.0, 10.0))


def test_snapping_engine_l_junctions():
    snapper = SnappingEngine(tolerance=0.20)
    report = ValidationReport()

    # Two walls meeting at corner with 0.10m gap
    w1 = WallEdge(id="W1", start=Point2D(0.0, 0.0), end=Point2D(5.0, 0.0))
    w2 = WallEdge(id="W2", start=Point2D(5.10, 0.05), end=Point2D(5.10, 5.0))

    snapped = snapper.snap_endpoints([w1, w2], report=report)
    assert len(snapped) == 2
    # Endpoints should now be identical
    assert snapped[0].end == snapped[1].start
    assert snapped[0].end.x == pytest.approx(5.05)
    assert snapped[0].end.y == pytest.approx(0.025)


def test_collinear_wall_merger():
    merger = CollinearWallMerger()
    report = ValidationReport()

    # Two collinear segments along X axis separated by a 1.0m door gap
    w1 = WallEdge(id="W1", start=Point2D(0.0, 0.0), end=Point2D(4.0, 0.0))
    w2 = WallEdge(id="W2", start=Point2D(5.0, 0.0), end=Point2D(10.0, 0.0))

    # Add opening on w2
    op2 = OpeningInterval(start_dist=1.0, end_dist=2.0, opening_type=OpeningType.WINDOW, id="WIN2")
    w2.add_opening(op2)

    merged = merger.merge_all([w1, w2], report=report)
    assert len(merged) == 1
    host = merged[0]
    assert host.length == pytest.approx(10.0)
    assert host.start == Point2D(0.0, 0.0)
    assert host.end == Point2D(10.0, 0.0)

    # Opening from w2 should have been re-parameterized to dist 6.0 to 7.0 on host wall
    assert len(host.openings) == 1
    assert host.openings[0].start_dist == pytest.approx(6.0)
    assert host.openings[0].end_dist == pytest.approx(7.0)


def test_opening_binder():
    binder = OpeningBinder()
    report = ValidationReport()

    wall = WallEdge(id="W1", start=Point2D(0.0, 0.0), end=Point2D(10.0, 0.0))

    # Raw opening centered at (5.0, 0.05) with width 1.2m
    raw_op = RawOpening(
        position=Point2D(5.0, 0.05),
        width=1.2,
        opening_type=OpeningType.DOOR,
        id="DOOR_TEST",
    )

    bound, unbound = binder.bind_openings([raw_op], [wall], report=report)
    assert bound == 1
    assert unbound == 0
    assert len(wall.openings) == 1
    assert wall.openings[0].start_dist == pytest.approx(4.4)
    assert wall.openings[0].end_dist == pytest.approx(5.6)


def test_room_topology_engine():
    engine = RoomTopologyEngine()
    report = ValidationReport()

    # Square room 4m x 5m
    pts = [Point2D(0.0, 0.0), Point2D(4.0, 0.0), Point2D(4.0, 5.0), Point2D(0.0, 5.0)]
    room = RoomPolygon(id="R1", name="Test Room", points=pts)

    assert room.area == pytest.approx(20.0)
    assert room.perimeter == pytest.approx(18.0)
    assert room.centroid.x == pytest.approx(2.0)
    assert room.centroid.y == pytest.approx(2.5)


def test_3tier_validator():
    validator = FloorPlanValidator()

    # Valid plan
    w1 = WallEdge(id="W1", start=Point2D(0.0, 0.0), end=Point2D(5.0, 0.0))
    w2 = WallEdge(id="W2", start=Point2D(5.0, 0.0), end=Point2D(5.0, 5.0))
    w3 = WallEdge(id="W3", start=Point2D(5.0, 5.0), end=Point2D(0.0, 5.0))
    w4 = WallEdge(id="W4", start=Point2D(0.0, 5.0), end=Point2D(0.0, 0.0))

    room = RoomPolygon(
        id="R1",
        name="Main",
        points=[Point2D(0.0, 0.0), Point2D(5.0, 0.0), Point2D(5.0, 5.0), Point2D(0.0, 5.0)],
    )

    plan = FloorPlan(walls=[w1, w2, w3, w4], rooms=[room])
    report = validator.validate(plan)

    assert report.has_errors is False
    assert report.error_count == 0
