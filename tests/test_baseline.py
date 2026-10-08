from evaluation.baseline import baseline_geometry
from integration.stubs import stub_analyze_floorplan
from integration.schemas import validate_against_schema


def test_baseline_geometry():
    masks = stub_analyze_floorplan("")
    scene = baseline_geometry(masks)
    assert validate_against_schema(scene) is True
    assert len(scene["walls"]) > 0
    assert len(scene["doors"]) > 0
    assert len(scene["rooms"]) > 0
