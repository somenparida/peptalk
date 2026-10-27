"""Geometry and topological cleanup engine for architectural floor plans."""

from src.geometry.binding import OpeningBinder, RawOpening
from src.geometry.graph import WallGraph
from src.geometry.merging import CollinearWallMerger
from src.geometry.rooms import RoomTopologyEngine
from src.geometry.snapping import SnappingEngine
from src.geometry.validator import FloorPlanValidator

__all__ = [
    "CollinearWallMerger",
    "FloorPlanValidator",
    "OpeningBinder",
    "RawOpening",
    "RoomTopologyEngine",
    "SnappingEngine",
    "WallGraph",
]
