import json
from enum import Enum
from pathlib import Path
from typing import List, Optional, Tuple, Dict, Any
import jsonschema
from pydantic import BaseModel, Field, FieldValidationInfo, field_validator

from .config import SCHEMA_PATH


class ProvenanceSource(str, Enum):
    DETECTED = "detected"
    INFERRED = "inferred"
    ESTIMATED = "estimated"


class ScaleSource(str, Enum):
    EXPLICIT = "explicit"
    REFERENCE = "reference"
    ESTIMATED = "estimated"


class SourceInfo(BaseModel):
    filename: str


class Scale(BaseModel):
    value: float = Field(..., gt=0)
    unit: str = "meters_per_pixel"
    source: ScaleSource
    confidence: float = Field(..., ge=0.0, le=1.0)


class Wall(BaseModel):
    id: str
    start: List[float] = Field(..., min_length=2, max_length=2)
    end: List[float] = Field(..., min_length=2, max_length=2)
    thickness: float = Field(..., gt=0)
    height: float = Field(..., gt=0)
    source: ProvenanceSource
    confidence: float = Field(..., ge=0.0, le=1.0)


class Door(BaseModel):
    id: str
    wall_id: str
    position: float = Field(..., ge=0.0, le=1.0)
    width: float = Field(..., gt=0)
    height: float = Field(..., gt=0)
    source: ProvenanceSource
    confidence: float = Field(..., ge=0.0, le=1.0)


class Window(BaseModel):
    id: str
    wall_id: str
    position: float = Field(..., ge=0.0, le=1.0)
    width: float = Field(..., gt=0)
    sill_height: float = Field(..., ge=0)
    height: float = Field(..., gt=0)
    source: ProvenanceSource
    confidence: float = Field(..., ge=0.0, le=1.0)


class Room(BaseModel):
    id: str
    label: Optional[str] = None
    polygon: List[List[float]] = Field(..., min_length=3)
    source: ProvenanceSource
    confidence: float = Field(..., ge=0.0, le=1.0)


class Scene(BaseModel):
    version: str = "1.0"
    units: str = "meters"
    source: Optional[SourceInfo] = None
    scale: Optional[Scale] = None
    walls: List[Wall] = Field(default_factory=list)
    doors: List[Door] = Field(default_factory=list)
    windows: List[Window] = Field(default_factory=list)
    rooms: List[Room] = Field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return json.loads(self.model_dump_json(exclude_none=True))

    @classmethod
    def load(cls, path: Path | str) -> "Scene":
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        validate_against_schema(data)
        return cls(**data)

    def save(self, path: Path | str) -> None:
        data = self.to_dict()
        validate_against_schema(data)
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)


def validate_against_schema(scene_dict: Dict[str, Any], schema_path: Path | str = SCHEMA_PATH) -> bool:
    """Validate a scene dictionary against the JSON schema file."""
    with open(schema_path, "r", encoding="utf-8") as f:
        schema = json.load(f)
    jsonschema.validate(instance=scene_dict, schema=schema)
    return True
