from integration.scale import parse_dimension_text, calibrate_scale, apply_scale
from integration.stubs import stub_reconstruct_geometry


def test_parse_dimension_text():
    assert parse_dimension_text("4500 mm") == 4.5
    assert parse_dimension_text("4.5 m") == 4.5
    assert parse_dimension_text("450 cm") == 4.5
    assert abs(parse_dimension_text("15ft 0in") - 4.572) < 1e-3


def test_calibrate_scale_door_reference():
    scene_px = stub_reconstruct_geometry({})
    mpp, src, conf, warnings = calibrate_scale(scene_px)
    assert src in ["reference", "estimated"]
    assert 0.001 <= mpp <= 0.1
    assert 0.0 <= conf <= 1.0


def test_apply_scale():
    scene_px = stub_reconstruct_geometry({})
    scene_m, warnings = apply_scale(scene_px, mpp=0.015, scale_source="explicit", confidence=0.9)
    assert scene_m["units"] == "meters"
    assert scene_m["scale"]["value"] == 0.015
    assert scene_m["walls"][0]["thickness"] == 0.06  # 4px * 0.015
