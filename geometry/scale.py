"""
Phase 4: Scale and Metric Conversion Module for Member 2.

Handles pixel -> meter conversions strictly when an authenticated or known scale is provided.
Never fabricates or invents measurements when scale is unknown.
"""

from __future__ import annotations

import copy
from typing import Dict, Any, Optional


def estimate_scale_from_reference(pixel_length: float, real_length_meters: float) -> float:
    """
    Estimates meters_per_pixel from a known physical reference measurement.
    Formula: meters_per_pixel = real_length_meters / pixel_length.
    """
    if pixel_length <= 0.0 or real_length_meters <= 0.0:
        raise ValueError("Both pixel_length and real_length_meters must be strictly positive.")
    return real_length_meters / pixel_length


def convert_to_metric(
    scene: Dict[str, Any],
    meters_per_pixel: float,
    source: str = "explicit",
    confidence: float = 1.0
) -> Dict[str, Any]:
    """
    Converts a scene's coordinates, dimensions, and areas from pixels to metric meters.
    """
    if meters_per_pixel <= 0.0:
        raise ValueError(f"meters_per_pixel must be positive (got {meters_per_pixel})")

    scaled_scene = copy.deepcopy(scene)
    s = meters_per_pixel
    s2 = s * s  # for area

    scaled_scene["units"] = "meters"
    scaled_scene["coordinate_system"] = "world"
    scaled_scene["scale"] = {
        "meters_per_pixel": round(s, 6),
        "source": source,
        "confidence": confidence,
        "metric_available": True
    }

    # Scale walls
    for w in scaled_scene.get("walls", []):
        geom = w["geometry"]
        geom["start"] = [round(geom["start"][0] * s, 4), round(geom["start"][1] * s, 4)]
        geom["end"] = [round(geom["end"][0] * s, 4), round(geom["end"][1] * s, 4)]
        geom["thickness"] = round(geom["thickness"] * s, 4)
        geom["length"] = round(geom["length"] * s, 4)
        w["start"] = list(geom["start"])
        w["end"] = list(geom["end"])
        w["thickness"] = geom["thickness"]

    # Scale doors
    for d in scaled_scene.get("doors", []):
        geom = d["geometry"]
        geom["center"] = [round(geom["center"][0] * s, 4), round(geom["center"][1] * s, 4)]
        geom["start"] = [round(geom["start"][0] * s, 4), round(geom["start"][1] * s, 4)]
        geom["end"] = [round(geom["end"][0] * s, 4), round(geom["end"][1] * s, 4)]
        geom["width"] = round(geom["width"] * s, 4)
        geom["offset_from_start"] = round(geom["offset_from_start"] * s, 4)
        d["width"] = geom["width"]

    # Scale windows
    for win in scaled_scene.get("windows", []):
        geom = win["geometry"]
        geom["center"] = [round(geom["center"][0] * s, 4), round(geom["center"][1] * s, 4)]
        geom["start"] = [round(geom["start"][0] * s, 4), round(geom["start"][1] * s, 4)]
        geom["end"] = [round(geom["end"][0] * s, 4), round(geom["end"][1] * s, 4)]
        geom["width"] = round(geom["width"] * s, 4)
        geom["offset_from_start"] = round(geom["offset_from_start"] * s, 4)
        win["width"] = geom["width"]

    # Scale rooms
    for r in scaled_scene.get("rooms", []):
        geom = r["geometry"]
        geom["polygon"] = [[round(p[0] * s, 4), round(p[1] * s, 4)] for p in geom["polygon"]]
        geom["area"] = round(geom["area"] * s2, 4)
        geom["perimeter"] = round(geom["perimeter"] * s, 4)
        geom["bounds"] = [round(b * s, 4) for b in geom["bounds"]]
        geom["centroid"] = [round(geom["centroid"][0] * s, 4), round(geom["centroid"][1] * s, 4)]
        r["polygon"] = list(geom["polygon"])

    return scaled_scene
