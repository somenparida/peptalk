"""Unified floor plan parsing pipeline with format auto-detection and validation."""

from __future__ import annotations

from pathlib import Path
from typing import Optional, Union

from src.geometry.merging import CollinearWallMerger
from src.geometry.snapping import SnappingEngine
from src.geometry.validator import FloorPlanValidator
from src.models import FloorPlan, ValidationLevel
from src.parser.image_detector import BlueprintImageDetector
from src.parser.structured_parser import StructuredFloorPlanParser


class FloorPlanParserPipeline:
    """
    Master ingestion pipeline for Mode A (Floor Plan -> 3D Model).
    Supports structured CAD JSON specifications and raster images (PNG, JPG).
    """

    def __init__(self, default_scale: float = 0.02) -> None:
        self.image_detector = BlueprintImageDetector(default_scale_m_per_px=default_scale)
        self.structured_parser = StructuredFloorPlanParser()
        self.snapper = SnappingEngine()
        self.merger = CollinearWallMerger()
        self.validator = FloorPlanValidator()

    def parse(self, input_path: Union[str, Path], scale: Optional[float] = None) -> FloorPlan:
        path = Path(input_path)
        if not path.exists():
            raise FileNotFoundError(f"Input floor plan file not found: {path}")

        suffix = path.suffix.lower()

        if suffix in (".json", ".geojson"):
            floor_plan = self.structured_parser.parse_file(path, scale=scale)
            # Post-cleanup: snap junctions and merge collinear segments
            floor_plan.walls = self.snapper.clean_and_snap(floor_plan.walls, report=floor_plan.validation)
            floor_plan.walls = self.merger.merge_all(floor_plan.walls, report=floor_plan.validation)
            floor_plan.walls = self.snapper.clean_and_snap(floor_plan.walls, report=floor_plan.validation)

        elif suffix in (".png", ".jpg", ".jpeg", ".bmp", ".tiff"):
            floor_plan = self.image_detector.parse_image(path, scale=scale)

        else:
            raise ValueError(
                f"Unsupported floor plan format '{suffix}'. Supported: PNG, JPG, JPEG, JSON."
            )

        # Run 3-Tier validation engine
        self.validator.validate(floor_plan)

        return floor_plan
