import pytest
from pathlib import Path
from integration.pipeline import reconstruct

BASE_DIR = Path(__file__).resolve().parent.parent


def test_pipeline_smoke(tmp_path):
    demo_img = BASE_DIR / "data" / "demo" / "demo_01.png"
    res = reconstruct(demo_img, out_root=tmp_path, mode="proposed")

    assert res["report"]["status"] == "success"
    assert Path(res["glb"]).exists()

    run_folder = tmp_path / demo_img.stem
    assert (run_folder / "scene.json").exists()
    assert (run_folder / "scene.glb").exists()
    assert (run_folder / "report.json").exists()
    assert (run_folder / "wall_mask.png").exists()
