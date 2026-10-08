"""
Geometry configuration constants and configurable tolerances for Member 2.
"""

# Snapping and merging tolerances (in pixels)
WALL_SNAP_TOLERANCE: float = 15.0       # Max distance between wall endpoints to snap together
WALL_MERGE_TOLERANCE: float = 10.0      # Max lateral offset to merge collinear wall segments
MIN_WALL_LENGTH: float = 15.0           # Walls shorter than this are flagged as suspicious/short
COLINEAR_ANGLE_TOLERANCE_DEG: float = 5.0 # Max angle difference (deg) to consider walls collinear
CORNER_SNAP_TOLERANCE: float = 15.0     # Max distance to snap an endpoint onto a nearby wall body

# Room validation
MIN_ROOM_VERTICES: int = 3
MIN_ROOM_AREA_PX: float = 50.0

# Architectural defaults
DEFAULT_WALL_HEIGHT_METERS: float = 3.0
DEFAULT_DOOR_HEIGHT_METERS: float = 2.1
DEFAULT_WINDOW_SILL_HEIGHT_METERS: float = 0.9
DEFAULT_WINDOW_HEIGHT_METERS: float = 1.2
