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
