"""
Room Processing Module for Member 2.

Validates room polygons, repairs minor geometric anomalies (winding/self-intersection buffer),
computes geometric metrics (area, perimeter, bounding box, centroid), and preserves source data.
"""

from __future__ import annotations

from typing import Dict, Any, List, Tuple
from shapely.geometry import Polygon


def process_rooms(rooms_data: List[Dict[str, Any]]) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """
    Validates and calculates geometric properties for room polygons.
    Returns (processed_rooms, room_issues).
    """
    processed: List[Dict[str, Any]] = []
    issues: List[Dict[str, Any]] = []

    for idx, r in enumerate(rooms_data):
        r_id = str(r.get("id", f"room_{idx+1}"))
        poly_pts = r.get("polygon", [])

        if not isinstance(poly_pts, list) or len(poly_pts) < 3:
            issues.append({
                "type": "invalid_room_polygon",
                "element_id": r_id,
                "element_type": "room",
                "severity": "error",
                "message": f"Room '{r_id}' polygon must have at least 3 vertices"
            })
            continue

        pts = [(float(p[0]), float(p[1])) for p in poly_pts]
        poly = Polygon(pts)

        if not poly.is_valid:
            poly = poly.buffer(0)
            issues.append({
                "type": "repaired_room_polygon",
                "element_id": r_id,
                "element_type": "room",
                "severity": "warning",
                "message": f"Room '{r_id}' polygon had invalid topology and was cleaned via buffer(0)"
            })

        area = round(float(poly.area), 2)
        perimeter = round(float(poly.length), 2)
        bounds = [round(float(b), 2) for b in poly.bounds]
        centroid = [round(float(poly.centroid.x), 2), round(float(poly.centroid.y), 2)]

        # Extract normalized polygon points
        clean_pts = [[round(p[0], 2), round(p[1], 2)] for p in poly.exterior.coords[:-1]]

        processed.append({
            "id": r_id,
            "label": r.get("label", r.get("name", r_id)),
            "source": {
                "polygon": [[float(p[0]), float(p[1])] for p in poly_pts]
            },
            "geometry": {
                "polygon": clean_pts,
                "area": area,
                "perimeter": perimeter,
                "bounds": bounds,
                "centroid": centroid,
                "num_vertices": len(clean_pts)
            },
            # Top-level mirrors for convenience
            "polygon": clean_pts
        })

    return processed, issues
