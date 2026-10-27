"""Unit tests for Stage 1: Blueprint Parser & Feature Extraction."""

import json
from pathlib import Path
import pytest

from src.parser.image_detector import BlueprintImageDetector
from src.parser.pipeline import FloorPlanParserPipeline
from src.parser.structured_parser import StructuredFloorPlanParser
from src.parser.synthetic_generator import SyntheticBenchmarkGenerator


def test_synthetic_benchmark_generator(tmp_path: Path):
    gen = SyntheticBenchmarkGenerator(pixels_per_meter=50.0)
    plan, plan_dict = gen.generate_apartment_plan()

    assert len(plan.walls) >= 8
    assert len(plan.rooms) == 6
    assert plan.total_area == pytest.approx(80.0, abs=1.0)

    # Test image rendering
    img, meta = gen.render_blueprint_image(plan)
    assert img.shape[0] > 300
    assert img.shape[1] > 400
    assert meta["pixels_per_meter"] == 50.0

    # Test export dataset
    img_file, json_file = gen.export_benchmark_dataset(tmp_path)
    assert img_file.exists()
    assert json_file.exists()


def test_structured_floorplan_parser(tmp_path: Path):
    parser = StructuredFloorPlanParser()

    spec = {
        "scale": 1.0,
        "walls": [
            {"id": "w1", "start": [0, 0], "end": [6, 0], "thickness": 0.2},
            {"id": "w2", "start": [6, 0], "end": [6, 4], "thickness": 0.2},
            {"id": "w3", "start": [6, 4], "end": [0, 4], "thickness": 0.2},
            {"id": "w4", "start": [0, 4], "end": [0, 0], "thickness": 0.2},
        ],
        "openings": [
            {"type": "DOOR", "position": [3.0, 0.0], "width": 1.0, "height": 2.1},
            {"type": "WINDOW", "position": [6.0, 2.0], "width": 1.2, "height": 1.2},
        ],
    }

    json_path = tmp_path / "simple_spec.json"
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(spec, f)

    plan = parser.parse_file(json_path)
    assert len(plan.walls) == 4
    # Check that openings were bound
    counts = plan.opening_counts
    assert counts["doors"] == 1
    assert counts["windows"] == 1
    # Check that room was polygonized
    assert len(plan.rooms) == 1
    assert plan.rooms[0].area == pytest.approx(24.0, abs=0.5)


def test_parser_pipeline_router(tmp_path: Path):
    pipeline = FloorPlanParserPipeline()
    gen = SyntheticBenchmarkGenerator(pixels_per_meter=50.0)
    _, json_path = gen.export_benchmark_dataset(tmp_path)

    plan = pipeline.parse(json_path)
    assert len(plan.walls) > 0
    assert len(plan.rooms) > 0
    assert not plan.validation.has_errors


def test_scale_bar_calibration_and_phantom_wall_suppression():
    """Regression test: verify scale bar detection and removal of scale bar phantom wall."""
    detector = BlueprintImageDetector()
    img_path = Path("data/benchmark/benchmark_floorplan.png")
    if not img_path.exists():
        pytest.skip("Benchmark floorplan not found.")

    plan = detector.parse_image(img_path)

    # 1. Scale should be calibrated from the CAD scale bar (~0.027 m/px)
    assert 0.020 <= plan.scale <= 0.035
    assert plan.metadata["uncertain_detections"]["scale"]["source"] == "scale_bar"
    assert plan.metadata["uncertain_detections"]["scale"]["confidence"] >= 0.90

    # 2. Scale bar line (y < 0.8m) must not be extracted as an isolated wall
    for w in plan.walls:
        mid_y = 0.5 * (w.start.y + w.end.y)
        # Scale bar is in bottom margin (y ~ 0.5m)
        if mid_y < 0.70:
            # If any wall is here, it should not be an isolated wall spanning the bottom margin
            assert w.length < 3.0, f"Detected unsuppressed scale bar wall: {w.id} with length {w.length}m"


def test_margin_border_artifact_suppression():
    """Regression test: verify that canvas boundary/scan margin lines are not parsed as walls."""
    detector = BlueprintImageDetector()
    img_path = Path("data/benchmark/blueprint3.jpg")
    if not img_path.exists():
        pytest.skip("blueprint3.jpg not found.")

    plan = detector.parse_image(img_path)

    # There should be no wall along x=0 spanning the full height of the image
    for w in plan.walls:
        if abs(w.start.x) < 0.05 and abs(w.end.x) < 0.05:
            assert w.length < 5.0, f"Detected scanner margin border line as wall: {w.id}"


def test_room_boundary_self_intersection_repair():
    """Regression test: verify self-intersecting room cavities from raster masks are repaired into valid simple polygons."""
    pipeline = FloorPlanParserPipeline()
    img_path = Path("data/input/test_floorplan.png")
    if not img_path.exists():
        pytest.skip("test_floorplan.png not found.")

    plan = pipeline.parse(img_path)

    assert not plan.validation.has_errors, f"Validation errors encountered: {[i.to_dict() for i in plan.validation.issues if i.level.value == 'ERROR']}"
    assert len(plan.rooms) >= 2
    for r in plan.rooms:
        poly = r.shapely_polygon
        assert poly.is_valid, f"Room {r.id} polygon is invalid: self-intersecting."
        assert not poly.is_empty
        assert r.area >= 1.0


def test_uncertain_detection_documentation():
    """Regression test: verify that uncertain detections are documented in metadata and validation report."""
    detector = BlueprintImageDetector()
    img_path = Path("data/input/test_floorplan.png")
    if not img_path.exists():
        pytest.skip("test_floorplan.png not found.")

    plan = detector.parse_image(img_path)

    assert "uncertain_detections" in plan.metadata
    unc = plan.metadata["uncertain_detections"]
    assert "scale" in unc
    assert "openings" in unc
    assert "rooms" in unc

    # Check that issues in validation report include audit information
    info_codes = {i.code for i in plan.validation.issues}
    assert "UNCERTAIN_DETECTIONS_DOCUMENTED" in info_codes or "DOOR_SCALE_CALIBRATED" in info_codes or "SCALE_BAR_DETECTED" in info_codes


def test_structured_parser_units_and_scene_schema_compatibility(tmp_path: Path):
    """Regression test: verify units conversion (mm, cm), top-level doors/windows, and polygon keys."""
    parser = StructuredFloorPlanParser()

    spec_mm = {
        "units": "mm",
        "wall_height": 3.0,
        "walls": [
            {"id": "w1", "start": [0, 0], "end": [5000, 0], "thickness": 200},
            {"id": "w2", "start": [5000, 0], "end": [5000, 4000], "thickness": 200},
            {"id": "w3", "start": [5000, 4000], "end": [0, 4000], "thickness": 200},
            {"id": "w4", "start": [0, 4000], "end": [0, 0], "thickness": 200},
        ],
        "doors": [
            {"id": "d1", "wall_id": "w1", "offset": 2000, "width": 900, "height": 2.1},
        ],
        "windows": [
            {"id": "win1", "wall_id": "w3", "offset": 1500, "width": 1200, "height": 1.2, "sill_height": 0.9},
        ],
        "rooms": [
            {
                "id": "r1",
                "name": "Main Hall",
                "polygon": [[0, 0], [5000, 0], [5000, 4000], [0, 4000]],
            }
        ],
    }

    json_path = tmp_path / "cad_spec_mm.json"
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(spec_mm, f)

    plan = parser.parse_file(json_path)

    # Scale should convert 5000mm to 5.0m
    assert plan.scale == pytest.approx(0.001)
    w1 = next(w for w in plan.walls if w.id == "w1")
    assert w1.length == pytest.approx(5.0, abs=0.01)
    assert len(w1.openings) == 1
    assert w1.openings[0].width == pytest.approx(0.90, abs=0.01)

    w3 = next(w for w in plan.walls if w.id == "w3")
    assert len(w3.openings) == 1
    assert w3.openings[0].width == pytest.approx(1.20, abs=0.01)

    assert len(plan.rooms) == 1
    assert plan.rooms[0].area == pytest.approx(20.0, abs=0.1)


def test_to_scene_dict_schema_compliance(tmp_path: Path):
    """Regression test: verify to_scene_dict produces exact scene schema specification."""
    pipeline = FloorPlanParserPipeline()
    img_path = Path("data/benchmark/benchmark_floorplan.png")
    if not img_path.exists():
        pytest.skip("benchmark_floorplan.png not found.")

    plan = pipeline.parse(img_path)
    scene_dict = plan.to_scene_dict()

    assert scene_dict["units"] == "meters"
    assert scene_dict["coordinate_system"]["up_axis"] == "Z"
    assert "walls" in scene_dict and len(scene_dict["walls"]) > 0
    assert "rooms" in scene_dict and len(scene_dict["rooms"]) > 0
    assert "doors" in scene_dict
    assert "windows" in scene_dict
    assert "metadata" in scene_dict

    # Check wall schema
    for w in scene_dict["walls"]:
        assert "id" in w
        assert len(w["start"]) == 2
        assert len(w["end"]) == 2
        assert w["thickness"] > 0

    # Check room schema
    for r in scene_dict["rooms"]:
        assert "id" in r
        assert "polygon" in r
        assert len(r["polygon"]) >= 3


def test_multichannel_floorplan_images_end_to_end():
    """Verify parser robustness on at least three distinct floor-plan image formats."""
    pipeline = FloorPlanParserPipeline()
    test_images = [
        Path("data/benchmark/benchmark_floorplan.png"),
        Path("data/benchmark/blueprint2.jpg"),
        Path("data/benchmark/blueprint3.jpg"),
        Path("data/input/test_floorplan.png"),
    ]

    available = [p for p in test_images if p.exists()]
    assert len(available) >= 3, f"Need at least 3 test images, found {len(available)}"

    results = []
    for img_path in available:
        plan = pipeline.parse(img_path)
        assert not plan.validation.has_errors, f"Errors in {img_path.name}: {[i.message for i in plan.validation.issues if i.level.value == 'ERROR']}"
        assert plan.scale > 0.0
        assert len(plan.walls) >= 4
        assert len(plan.rooms) >= 1
        for r in plan.rooms:
            assert r.shapely_polygon.is_valid
            assert r.area >= 1.0
        results.append({
            "image": img_path.name,
            "scale": plan.scale,
            "walls": len(plan.walls),
            "rooms": len(plan.rooms),
            "openings": plan.opening_counts,
            "total_area": round(plan.total_area, 2),
        })

    print("\nEnd-to-end multi-image parsing results:")
    for res in results:
        print(f"  {res['image']}: scale={res['scale']:.5f} m/px, walls={res['walls']}, rooms={res['rooms']}, area={res['total_area']}m²")

