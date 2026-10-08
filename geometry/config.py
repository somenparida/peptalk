"""
Geometry configuration constants and configurable tolerances for Member 2.
"""

# Configurable topology tolerances (in pixels)
TOPOLOGY_SNAP_TOLERANCE: float = 15.0       # Max distance between endpoints to snap together
WALL_SNAP_TOLERANCE: float = 15.0           # Alias for backward compatibility
WALL_MERGE_TOLERANCE: float = 15.0          # Max lateral offset to merge collinear wall segments
COLINEAR_ANGLE_TOLERANCE_DEG: float = 8.0   # Max angle difference (deg) to consider walls collinear
CORNER_SNAP_TOLERANCE: float = 15.0         # Max distance to snap an endpoint onto a nearby wall body (T-junction)
MIN_WALL_LENGTH: float = 15.0               # Walls shorter than this are flagged as suspicious/short

# Behavior toggles
MERGE_COLLINEAR_FRAGMENTS: bool = True      # Merge collinear wall segments interrupted by openings
REMOVE_EXTRACTION_ARTIFACTS: bool = True    # Safely retire tiny non-structural line artifacts in opening gaps

# Room validation thresholds
MIN_ROOM_VERTICES: int = 3
MIN_ROOM_AREA_PX: float = 50.0

# Architectural defaults
DEFAULT_WALL_HEIGHT_METERS: float = 3.0
DEFAULT_DOOR_HEIGHT_METERS: float = 2.1
DEFAULT_WINDOW_SILL_HEIGHT_METERS: float = 0.9
DEFAULT_WINDOW_HEIGHT_METERS: float = 1.2
