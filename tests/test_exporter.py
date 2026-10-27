"""Unit tests for Stage 4: GLB Exporter."""

from pathlib import Path
import trimesh

from src.builder.scene_builder import ArchitecturalSceneBuilder
from src.exporter.glb_exporter import GLBSceneExporter
from src.models import FloorPlan, Point2D, RoomPolygon, WallEdge


def test_glb_scene_exporter(tmp_path: Path):
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

    scene_builder = ArchitecturalSceneBuilder()
    scene = scene_builder.build_scene(plan)

    exporter = GLBSceneExporter()
    out_glb = tmp_path / "test_model.glb"
    res_path = exporter.export(scene, out_glb, floor_plan=plan)

    assert res_path.exists()
    assert res_path.stat().st_size > 500  # valid binary GLB size

    # Companion metadata file
    meta_path = tmp_path / "test_model_metadata.json"
    assert meta_path.exists()

    # Verify that Trimesh can load it back
    loaded_scene = trimesh.load(res_path, file_type="glb")
    assert isinstance(loaded_scene, trimesh.Scene)
    assert len(loaded_scene.geometry) > 0
