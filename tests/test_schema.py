import json
import pytest
from pathlib import Path
from integration.schemas import Scene, validate_against_schema

BASE_DIR = Path(__file__).resolve().parent.parent


def test_valid_scene_schema():
    example_path = BASE_DIR / "data" / "expected" / "example.json"
    scene = Scene.load(example_path)
    assert scene.version == "1.0"
    assert len(scene.walls) == 4
    assert len(scene.doors) == 1
    assert len(scene.windows) == 1
    assert len(scene.rooms) == 1


def test_invalid_scene_schema():
    invalid_dict = {
        "version": "1.0",
        "units": "meters",
        "walls": [
            {
                "id": "wall_bad",
                "start": [0, 0],
                "end": [5, 0],
                "thickness": -0.2,  # Invalid thickness <= 0
                "height": 3.0,
                "source": "detected",
                "confidence": 1.5,  # Invalid confidence > 1.0
            }
        ],
        "doors": [],
        "windows": [],
        "rooms": [],
    }
    with pytest.raises(Exception):
        validate_against_schema(invalid_dict)
