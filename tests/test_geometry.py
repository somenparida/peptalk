"""Unit tests for Stage 2: Topological Graph & Geometry Cleanup Engine."""

import math
from pathlib import Path
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
from src.parser.image_detector import BlueprintImageDetector


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


def test_preserve_partition_wall_w9_documented_notice():
    """
    Regression Test: Dead-end partition wall 'w9' must be preserved as source geometry
    when evidence is insufficient to snap or prune, and documented with a DEAD_END_WALL notice.
    """
    # Outer rectangular boundary: 10m x 8m
    w1 = WallEdge(id="w1", start=Point2D(0.0, 0.0), end=Point2D(10.0, 0.0))
    w2 = WallEdge(id="w2", start=Point2D(10.0, 0.0), end=Point2D(10.0, 8.0))
    w3 = WallEdge(id="w3", start=Point2D(10.0, 8.0), end=Point2D(0.0, 8.0))
    w4 = WallEdge(id="w4", start=Point2D(0.0, 8.0), end=Point2D(0.0, 0.0))

    # Dead-end partition wall 'w9' projecting into the room from w1
    # T-junction at (4.0, 0.0), floating end at (4.0, 3.5)
    w9 = WallEdge(id="w9", start=Point2D(4.0, 0.0), end=Point2D(4.0, 3.5), thickness=0.15)

    initial_walls = [w1, w2, w3, w4, w9]
    report = ValidationReport()

    # 1. Snapping: Must snap T-junction at (4.0, 0.0) without collapsing or deleting w9
    snapper = SnappingEngine(tolerance=0.20)
    snapped = snapper.clean_and_snap(initial_walls, report=report)
    wall_ids = [w.id for w in snapped]
    assert any("w9" in wid for wid in wall_ids), "w9 must survive snapping"

    # 2. Merging: Collinear merger must preserve w9 perpendicular partition
    merger = CollinearWallMerger()
    merged = merger.merge_all(snapped, report=report)
    merged_ids = [w.id for w in merged]
    assert any("w9" in wid for wid in merged_ids), "w9 must survive collinear merging"

    # 3. Validation: Validator must preserve w9 and document DEAD_END_WALL notice
    plan = FloorPlan(walls=merged)
    validator = FloorPlanValidator()
    val_report = validator.validate(plan)

    assert val_report.has_errors is False, "Dead-end partition must not cause blocking errors"
    
    # Check for documented w9 notice
    dead_end_issues = [
        issue for issue in val_report.issues 
        if issue.code == "DEAD_END_WALL" and issue.entity_id and "w9" in issue.entity_id
    ]
    assert len(dead_end_issues) >= 1, "Must document DEAD_END_WALL notice for w9"
    assert "Preserving source geometry" in dead_end_issues[0].message


def test_dimensional_consistency_door_and_window_audits():
    """
    Regression Test: Dimensional consistency checks must detect abnormal wall thicknesses,
    heights, door widths, floating door sills, and apertures exceeding wall height.
    """
    validator = FloorPlanValidator()

    # Wall 1: Very thick wall (0.90m) and non-standard height (1.5m)
    w1 = WallEdge(id="w_thick", start=Point2D(0.0, 0.0), end=Point2D(6.0, 0.0), thickness=0.90, height=1.50)
    
    # Door with floating sill (0.40m) and narrow width (0.45m)
    door_floating = OpeningInterval(
        start_dist=1.0, end_dist=1.45, opening_type=OpeningType.DOOR, id="door_narrow", sill_height=0.40, height=2.10
    )
    w1.openings.append(door_floating)

    # Window exceeding wall height: sill 0.8m + height 1.2m = 2.0m > wall height 1.5m
    win_exceed = OpeningInterval(
        start_dist=3.0, end_dist=4.5, opening_type=OpeningType.WINDOW, id="win_tall", sill_height=0.80, height=1.20
    )
    w1.openings.append(win_exceed)

    plan = FloorPlan(walls=[w1])
    report = validator.validate(plan)

    issue_codes = {i.code for i in report.issues}
    assert "UNUSUAL_WALL_THICKNESS" in issue_codes
    assert "UNUSUAL_WALL_HEIGHT" in issue_codes
    assert "DOOR_FLOATING_SILL" in issue_codes
    assert "DOOR_TOO_NARROW" in issue_codes
    assert "OPENING_EXCEEDS_WALL_HEIGHT" in issue_codes


def test_t_junction_opening_distribution_regression():
    """
    Regression Test: Host wall splitting at T-junction must accurately re-parameterize
    all existing opening intervals without aperture loss or geometric coordinate drift.
    """
    snapper = SnappingEngine(tolerance=0.20)
    report = ValidationReport()

    # Host wall of 10m length with door at [1.0, 2.0] and window at [7.0, 8.5]
    host = WallEdge(id="W_HOST", start=Point2D(0.0, 0.0), end=Point2D(10.0, 0.0))
    door = OpeningInterval(start_dist=1.0, end_dist=2.0, opening_type=OpeningType.DOOR, id="DOOR_1")
    win = OpeningInterval(start_dist=7.0, end_dist=8.5, opening_type=OpeningType.WINDOW, id="WIN_1")
    host.add_opening(door)
    host.add_opening(win)

    # Perpendicular wall meeting host at (5.0, 0.0) -> T-junction
    perp = WallEdge(id="W_PERP", start=Point2D(5.0, 0.05), end=Point2D(5.0, 5.0))

    snapped = snapper.snap_t_junctions([host, perp], report=report)
    assert len(snapped) == 3

    # Find split segments of W_HOST
    part_a = next(w for w in snapped if w.id == "W_HOST_a")
    part_b = next(w for w in snapped if w.id == "W_HOST_b")

    # Part A [0.0 to 5.0]: Contains DOOR_1 at [1.0, 2.0]
    assert part_a.length == pytest.approx(5.0)
    assert len(part_a.openings) == 1
    assert part_a.openings[0].id == "DOOR_1"
    assert part_a.openings[0].start_dist == pytest.approx(1.0)
    assert part_a.openings[0].end_dist == pytest.approx(2.0)

    # Part B [5.0 to 10.0]: Contains WIN_1 re-parameterized to [2.0, 3.5]
    assert part_b.length == pytest.approx(5.0)
    assert len(part_b.openings) == 1
    assert part_b.openings[0].id == "WIN_1"
    assert part_b.openings[0].start_dist == pytest.approx(2.0)
    assert part_b.openings[0].end_dist == pytest.approx(3.5)


def test_collinear_merging_opening_reparameterization():
    """
    Regression Test: Collinear wall segments separated by a gap must merge into a single
    continuous host wall with preserved opening intervals mapped along the unified axis.
    """
    merger = CollinearWallMerger(max_gap=2.5)
    report = ValidationReport()

    # Two collinear wall segments along X axis
    # W1: [0, 0] to [4, 0] with window at [1.0, 2.5]
    # W2: [5.5, 0] to [9.5, 0] with door at [1.0, 2.2]
    w1 = WallEdge(id="W1", start=Point2D(0.0, 0.0), end=Point2D(4.0, 0.0))
    w1.add_opening(OpeningInterval(start_dist=1.0, end_dist=2.5, opening_type=OpeningType.WINDOW, id="W1_WIN"))

    w2 = WallEdge(id="W2", start=Point2D(5.5, 0.0), end=Point2D(9.5, 0.0))
    w2.add_opening(OpeningInterval(start_dist=1.0, end_dist=2.2, opening_type=OpeningType.DOOR, id="W2_DOOR"))

    merged = merger.merge_all([w1, w2], report=report)
    assert len(merged) == 1
    host = merged[0]

    assert host.length == pytest.approx(9.5)
    assert len(host.openings) == 2

    # Openings should be sorted along host wall
    op_win = next(op for op in host.openings if op.opening_type == OpeningType.WINDOW)
    op_door = next(op for op in host.openings if op.opening_type == OpeningType.DOOR)

    assert op_win.start_dist == pytest.approx(1.0)
    assert op_win.end_dist == pytest.approx(2.5)
    # W2 starts at 5.5m along host wall, so [1.0, 2.2] on W2 -> [6.5, 7.7] on host
    assert op_door.start_dist == pytest.approx(6.5)
    assert op_door.end_dist == pytest.approx(7.7)


def test_room_closure_multi_loop_extraction():
    """
    Regression Test: Extraction of closed room polygon topology from a 2x2 multi-room grid.
    """
    engine = RoomTopologyEngine()
    report = ValidationReport()

    # 2x2 grid: rooms are [0..3, 0..3], [3..6, 0..3], [0..3, 3..6], [3..6, 3..6]
    walls = [
        # Horizontal lines at y=0, y=3, y=6
        WallEdge(id="h0_1", start=Point2D(0.0, 0.0), end=Point2D(3.0, 0.0)),
        WallEdge(id="h0_2", start=Point2D(3.0, 0.0), end=Point2D(6.0, 0.0)),
        WallEdge(id="h3_1", start=Point2D(0.0, 3.0), end=Point2D(3.0, 3.0)),
        WallEdge(id="h3_2", start=Point2D(3.0, 3.0), end=Point2D(6.0, 3.0)),
        WallEdge(id="h6_1", start=Point2D(0.0, 6.0), end=Point2D(3.0, 6.0)),
        WallEdge(id="h6_2", start=Point2D(3.0, 6.0), end=Point2D(6.0, 6.0)),
        # Vertical lines at x=0, x=3, x=6
        WallEdge(id="v0_1", start=Point2D(0.0, 0.0), end=Point2D(0.0, 3.0)),
        WallEdge(id="v0_2", start=Point2D(0.0, 3.0), end=Point2D(0.0, 6.0)),
        WallEdge(id="v3_1", start=Point2D(3.0, 0.0), end=Point2D(3.0, 3.0)),
        WallEdge(id="v3_2", start=Point2D(3.0, 3.0), end=Point2D(3.0, 6.0)),
        WallEdge(id="v6_1", start=Point2D(6.0, 0.0), end=Point2D(6.0, 3.0)),
        WallEdge(id="v6_2", start=Point2D(6.0, 3.0), end=Point2D(6.0, 6.0)),
    ]

    rooms = engine.extract_rooms_from_walls(walls, report=report)
    assert len(rooms) == 4, "Must discover exactly 4 enclosed rooms in a 2x2 wall grid"

    total_area = sum(r.area for r in rooms)
    assert total_area == pytest.approx(36.0, abs=0.1)
    for r in rooms:
        assert r.area == pytest.approx(9.0, abs=0.1)
        assert r.shapely_polygon.is_valid


def test_geometry_repair_against_actual_member1_outputs():
    """
    Integration & Regression Test: Validates Member 2 geometry engine and 3-Tier validator
    against actual CV parser outputs from Member 1 across benchmark blueprints.
    """
    detector = BlueprintImageDetector()
    validator = FloorPlanValidator()

    benchmark_path = Path("data/benchmark/blueprint2.jpg")
    assert benchmark_path.exists(), "Blueprint benchmark file must exist"

    # Member 1 output ingestion
    plan = detector.parse_image(benchmark_path)

    assert len(plan.walls) > 0, "Member 1 parser must produce walls"
    assert len(plan.rooms) > 0, "Must recover enclosed rooms"

    # Verify Member 2 geometry validation
    report = validator.validate(plan)
    assert report.has_errors is False, "Floor plan from Member 1 must not produce blocking errors"

    # Verify wall connection and opening bounds
    for w in plan.walls:
        assert w.length >= CONFIG.MIN_WALL_LENGTH
        for op in w.openings:
            assert op.start_dist >= 0.0
            assert op.end_dist <= w.length + 1e-3
            assert op.width > 0.0

