"""End-to-End Pipeline Integration Tests."""

from pathlib import Path
import pytest
import trimesh

from src.builder.scene_builder import ArchitecturalSceneBuilder
from src.exporter.glb_exporter import GLBSceneExporter
from src.parser.pipeline import FloorPlanParserPipeline
from src.parser.synthetic_generator import SyntheticBenchmarkGenerator


def test_full_pipeline_from_ground_truth(tmp_path: Path):
    # 1. Generate Synthetic Benchmark
    gen = SyntheticBenchmarkGenerator(pixels_per_meter=50.0)
    img_path, json_path = gen.export_benchmark_dataset(tmp_path)

    # 2. Ingest through Stage 1 & 2 Pipeline
    pipeline = FloorPlanParserPipeline()
    plan = pipeline.parse(json_path)

    assert not plan.validation.has_errors
    assert len(plan.walls) >= 4
    assert len(plan.rooms) >= 4

    # 3. Stage 3: Procedural 3D Reconstruction
    scene_builder = ArchitecturalSceneBuilder()
    scene = scene_builder.build_scene(plan)

    assert "Walls" in scene.geometry
    assert "Floors" in scene.geometry
    assert "Ceilings" in scene.geometry

    # 4. Stage 4: GLB Export
    exporter = GLBSceneExporter()
    glb_out = tmp_path / "e2e_scene.glb"
    res_path = exporter.export(scene, glb_out, floor_plan=plan)

    assert res_path.exists()
    assert res_path.stat().st_size > 1000

    # 5. Verify integrity of exported GLB
    loaded = trimesh.load(res_path, file_type="glb")
    assert isinstance(loaded, trimesh.Scene)
    assert len(loaded.geometry) >= 3


def test_full_pipeline_from_blueprint_image(tmp_path: Path):
    # 1. Generate Synthetic Benchmark
    gen = SyntheticBenchmarkGenerator(pixels_per_meter=50.0)
    img_path, _ = gen.export_benchmark_dataset(tmp_path)

    # 2. Ingest raster image
    pipeline = FloorPlanParserPipeline()
    plan = pipeline.parse(img_path)

    assert len(plan.walls) > 0
    assert not plan.validation.has_errors

    # 3. Reconstruct 3D meshes
    scene_builder = ArchitecturalSceneBuilder()
    scene = scene_builder.build_scene(plan)

    # 4. Export GLB
    exporter = GLBSceneExporter()
    glb_out = tmp_path / "e2e_image_scene.glb"
    res_path = exporter.export(scene, glb_out, floor_plan=plan)

    assert res_path.exists()
    assert res_path.stat().st_size > 500
