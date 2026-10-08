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
        d["width"] = round(float(d.get("width", 0.0)) * s, 4)
        if "height" in d:
            d["height"] = round(float(d["height"]) * s, 4)
        if "offset" in d:
            d["offset"] = round(float(d["offset"]) * s, 4)
        if "opening_start" in d:
            d["opening_start"] = round(float(d["opening_start"]) * s, 4)
        if "opening_end" in d:
            d["opening_end"] = round(float(d["opening_end"]) * s, 4)

        geom = d.setdefault("geometry", {})
        if "center" in geom:
            geom["center"] = [round(geom["center"][0] * s, 4), round(geom["center"][1] * s, 4)]
        if "start" in geom:
            geom["start"] = [round(geom["start"][0] * s, 4), round(geom["start"][1] * s, 4)]
        if "end" in geom:
            geom["end"] = [round(geom["end"][0] * s, 4), round(geom["end"][1] * s, 4)]
        if "opening_start" in geom:
            geom["opening_start"] = round(geom["opening_start"] * s, 4)
        if "opening_end" in geom:
            geom["opening_end"] = round(geom["opening_end"] * s, 4)
        geom["width"] = d["width"]
        if "offset" in d:
            geom["offset"] = d["offset"]

    # Scale windows
    for win in scaled_scene.get("windows", []):
        win["width"] = round(float(win.get("width", 0.0)) * s, 4)
        if "height" in win:
            win["height"] = round(float(win["height"]) * s, 4)
        if "sill_height" in win:
            win["sill_height"] = round(float(win["sill_height"]) * s, 4)
        if "offset" in win:
            win["offset"] = round(float(win["offset"]) * s, 4)
        if "opening_start" in win:
            win["opening_start"] = round(float(win["opening_start"]) * s, 4)
        if "opening_end" in win:
            win["opening_end"] = round(float(win["opening_end"]) * s, 4)

        geom = win.setdefault("geometry", {})
        if "center" in geom:
            geom["center"] = [round(geom["center"][0] * s, 4), round(geom["center"][1] * s, 4)]
        if "start" in geom:
            geom["start"] = [round(geom["start"][0] * s, 4), round(geom["start"][1] * s, 4)]
        if "end" in geom:
            geom["end"] = [round(geom["end"][0] * s, 4), round(geom["end"][1] * s, 4)]
        if "opening_start" in geom:
            geom["opening_start"] = round(geom["opening_start"] * s, 4)
        if "opening_end" in geom:
            geom["opening_end"] = round(geom["opening_end"] * s, 4)
        geom["width"] = win["width"]
        if "offset" in win:
            geom["offset"] = win["offset"]

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
