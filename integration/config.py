import os
from pathlib import Path

# Paths
BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
OUTPUTS_DIR = BASE_DIR / "outputs"
SCHEMA_PATH = BASE_DIR / "scene_schema.json"

# Defaults for 3D generation & geometry
DEFAULT_WALL_HEIGHT = 3.0       # meters
DEFAULT_WALL_THICKNESS = 0.20   # meters
DEFAULT_DOOR_HEIGHT = 2.10     # meters
DEFAULT_DOOR_WIDTH = 0.90       # meters
DEFAULT_WINDOW_SILL_HEIGHT = 0.90 # meters
DEFAULT_WINDOW_HEIGHT = 1.20    # meters

# Disconnected wall tolerance factor (tolerance = TOL_FACTOR * wall_thickness)
DISCONNECTED_WALL_TOL_FACTOR = 2.0

# Scale Calibration Bounds (Sanity Checks)
SANITY_MIN_ROOM_WIDTH = 1.0       # meters
SANITY_MAX_BUILDING_WIDTH = 200.0 # meters
SANITY_MIN_WALL_THICKNESS = 0.05  # meters
SANITY_MAX_WALL_THICKNESS = 0.60  # meters
SANITY_MIN_DOOR_WIDTH = 0.60      # meters
SANITY_MAX_DOOR_WIDTH = 1.50      # meters

# Fallback estimated MPP (meters per pixel) if all calibration methods fail
DEFAULT_ESTIMATED_MPP = 0.015

# Evaluation Composite Score Weights (IoU 40, Dimension 25, Completeness 20, Validity 15)
WEIGHT_IOU = 0.40
WEIGHT_DIMENSION = 0.25
WEIGHT_COMPLETENESS = 0.20
WEIGHT_VALIDITY = 0.15
