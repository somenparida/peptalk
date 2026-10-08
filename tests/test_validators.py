import pytest
from pathlib import Path
from integration.validators import validate_input, validate_scene
from integration.schemas import Scene

BASE_DIR = Path(__file__).resolve().parent.parent


def test_validate_input_missing_file():
    with pytest.raises(FileNotFoundError):
        validate_input("non_existent_file.png")


def test_validate_input_unsupported_ext(tmp_path):
    txt_file = tmp_path / "test.txt"
    txt_file.write_text("dummy")
    with pytest.raises(ValueError):
        validate_input(txt_file)


def test_validate_scene_valid():
    example_path = BASE_DIR / "data" / "expected" / "example.json"
    scene = Scene.load(example_path)
    ok, errors, warnings, counters = validate_scene(scene)
    assert ok is True
    assert len(errors) == 0
    assert counters["invalid_walls"] == 0
    assert counters["disconnected_walls"] == 0


def test_validate_scene_disconnected_wall():
    bad_scene = {
        "version": "1.0",
        "units": "meters",
        "walls": [
            {
                "id": "wall_01",
                "start": [0.0, 0.0],
                "end": [5.0, 0.0],
                "thickness": 0.20,
                "height": 3.0,
                "source": "detected",
                "confidence": 0.9,
            },
            {
                "id": "wall_disconnected",
                "start": [50.0, 50.0],  # Far away endpoint
                "end": [55.0, 50.0],
                "thickness": 0.20,
                "height": 3.0,
                "source": "detected",
                "confidence": 0.9,
            },
        ],
        "doors": [],
        "windows": [],
        "rooms": [],
    }
    ok, errors, warnings, counters = validate_scene(bad_scene)
    assert counters["disconnected_walls"] >= 1
