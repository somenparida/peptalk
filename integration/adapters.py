import logging
from pathlib import Path
from typing import Callable, Tuple, Dict, Any
import numpy as np
from PIL import Image

from .stubs import (
    stub_analyze_floorplan,
    stub_reconstruct_geometry,
    stub_generate_3d,
)

log = logging.getLogger(__name__)


def sanitize_mask(mask: Any) -> np.ndarray:
    """Ensure a mask output is a 2D numpy uint8 array (0 or 255)."""
    if isinstance(mask, (str, Path)):
        img = Image.open(mask).convert("L")
        arr = np.array(img, dtype=np.uint8)
    elif isinstance(mask, Image.Image):
        arr = np.array(mask.convert("L"), dtype=np.uint8)
    elif isinstance(mask, np.ndarray):
        arr = mask.astype(np.uint8)
        if arr.ndim == 3:
            arr = arr[:, :, 0]
    else:
        raise ValueError(f"Unsupported mask data type: {type(mask)}")
    return arr


def load_ai() -> Tuple[Callable, str]:
    """Load real AI segmentation module if available, otherwise return stub."""
    try:
        from ai.inference import analyze_floorplan
        log.info("Loaded REAL AI module (ai.inference)")
        return analyze_floorplan, "real"
    except Exception as e1:
        try:
            from ai import analyze_floorplan
            log.info("Loaded REAL AI module (ai)")
            return analyze_floorplan, "real"
        except Exception as e2:
            log.warning("AI module unavailable (%s); using STUB", e1)
            return stub_analyze_floorplan, "stub"


def load_geometry() -> Tuple[Callable, str]:
    """Load real geometry reconstruction module if available, otherwise return stub."""
    try:
        from geometry.reconstruction import reconstruct_geometry
        log.info("Loaded REAL Geometry module (geometry.reconstruction)")
        return reconstruct_geometry, "real"
    except Exception as e1:
        try:
            from geometry import reconstruct_geometry
            log.info("Loaded REAL Geometry module (geometry)")
            return reconstruct_geometry, "real"
        except Exception as e2:
            log.warning("Geometry module unavailable (%s); using STUB", e1)
            return stub_reconstruct_geometry, "stub"


def load_3d() -> Tuple[Callable, str]:
    """Load real 3D generation module if available, otherwise return stub."""
    try:
        from reconstruction.export import generate_3d
        log.info("Loaded REAL 3D module (reconstruction.export)")
        return generate_3d, "real"
    except Exception as e1:
        try:
            from viewer import generate_3d
            log.info("Loaded REAL 3D module (viewer)")
            return generate_3d, "real"
        except Exception as e2:
            log.warning("3D export module unavailable (%s); using STUB", e1)
            return stub_generate_3d, "stub"
