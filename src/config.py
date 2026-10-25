"""Configuration and standard architectural parameters for HNX26EPS06."""

from dataclasses import dataclass
from typing import Tuple


@dataclass(frozen=True)
class ArchitecturalDefaults:
    """Standard architectural dimensions in meters (SI units)."""
    # Wall dimensions
    WALL_HEIGHT: float = 2.80
    WALL_THICKNESS: float = 0.20
    MIN_WALL_LENGTH: float = 0.15

    # Door dimensions
    DOOR_HEIGHT: float = 2.10
    DOOR_WIDTH_DEFAULT: float = 0.90
    DOOR_FRAME_THICKNESS: float = 0.05
    DOOR_FRAME_DEPTH: float = 0.22

    # Window dimensions
    WINDOW_HEIGHT: float = 1.20
    WINDOW_SILL_HEIGHT: float = 0.90
    WINDOW_WIDTH_DEFAULT: float = 1.20
    WINDOW_FRAME_THICKNESS: float = 0.04
    WINDOW_SILL_OVERHANG: float = 0.04
    WINDOW_SILL_THICKNESS: float = 0.05

    # Slab dimensions
    FLOOR_SLAB_THICKNESS: float = 0.15
    CEILING_SLAB_THICKNESS: float = 0.12
    PLINTH_OFFSET: float = 0.05

    # Snapping & cleanup tolerances (meters)
    SNAP_TOLERANCE_METERS: float = 0.15
    COLLINEAR_ANGLE_MAX_DEG: float = 6.0
    COLLINEAR_MAX_DISTANCE: float = 0.12
    JUNCTION_SNAP_DIST: float = 0.18

    # Semantic RGBA Colors [0-255]
    COLOR_WALL: Tuple[int, int, int, int] = (245, 243, 238, 255)
    COLOR_WALL_EDGE: Tuple[int, int, int, int] = (100, 95, 90, 255)
    COLOR_FLOOR: Tuple[int, int, int, int] = (220, 212, 198, 255)
    COLOR_CEILING: Tuple[int, int, int, int] = (250, 250, 250, 255)
    COLOR_DOOR_LEAF: Tuple[int, int, int, int] = (180, 115, 60, 255)
    COLOR_DOOR_PANEL: Tuple[int, int, int, int] = (150, 90, 45, 255)
    COLOR_DOOR_FRAME: Tuple[int, int, int, int] = (95, 60, 35, 255)
    COLOR_DOOR_HANDLE: Tuple[int, int, int, int] = (225, 185, 75, 255)
    COLOR_WINDOW_GLASS: Tuple[int, int, int, int] = (140, 210, 245, 100)
    COLOR_WINDOW_FRAME: Tuple[int, int, int, int] = (115, 80, 52, 255)
    COLOR_WINDOW_MULLION: Tuple[int, int, int, int] = (100, 68, 44, 255)
    COLOR_WINDOW_SILL: Tuple[int, int, int, int] = (240, 235, 222, 255)
    COLOR_LINTEL: Tuple[int, int, int, int] = (238, 235, 230, 255)


# Global singleton instance
CONFIG = ArchitecturalDefaults()
