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
        from geometry.adapter import SceneAdapter
        from geometry.scene_graph import SceneGraph

        def real_geometry_wrapper(masks_or_dict: Dict[str, Any]) -> Dict[str, Any]:
            if "walls" in masks_or_dict:
                return masks_or_dict
            from .stubs import stub_reconstruct_geometry
            return stub_reconstruct_geometry(masks_or_dict)

        log.info("Loaded REAL Geometry engine (geometry.scene_graph)")
        return real_geometry_wrapper, "real"
    except Exception as e:
        log.warning("Geometry module unavailable (%s); using STUB", e)
        return stub_reconstruct_geometry, "stub"


def load_3d() -> Tuple[Callable, str]:
    """Load real 3D generation module if available, otherwise return stub."""
    try:
        from geometry.adapter import SceneAdapter
        from geometry.scene_graph import SceneGraph
        from geometry.exporter import SceneExporter

        def real_3d_wrapper(scene_data: Dict[str, Any], out_path: Path | str) -> str:
            spec = SceneAdapter.normalize(scene_data)
            graph = SceneGraph.from_specification(spec)
            out_file = SceneExporter.export(graph, str(out_path), file_format="glb")
            return str(out_file)

        log.info("Loaded REAL 3D export engine (geometry.exporter)")
        return real_3d_wrapper, "real"
    except Exception as e:
        log.warning("3D export module unavailable (%s); using STUB", e)
        return stub_generate_3d, "stub"
