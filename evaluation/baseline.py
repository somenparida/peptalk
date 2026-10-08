import math
from typing import Dict, Any, List, Tuple
import numpy as np
import cv2

from integration.config import (
    DEFAULT_ESTIMATED_MPP,
    DEFAULT_WALL_HEIGHT,
    DEFAULT_WALL_THICKNESS,
    DEFAULT_DOOR_HEIGHT,
    DEFAULT_DOOR_WIDTH,
    DEFAULT_WINDOW_SILL_HEIGHT,
    DEFAULT_WINDOW_HEIGHT,
)
from integration.schemas import Scene, validate_against_schema


def baseline_geometry(
    masks: Dict[str, np.ndarray],
    default_mpp: float = DEFAULT_ESTIMATED_MPP
) -> Dict[str, Any]:
    """
    Naive baseline geometry generator directly extracting raw contours from masks.
    Deliberately excludes topology correction, collinear merging, snapping, or validation repair.
    """
    wall_mask = masks.get("wall_mask")
    door_mask = masks.get("door_mask")
    window_mask = masks.get("window_mask")
    floor_mask = masks.get("floor_mask")

    if wall_mask is None:
        wall_mask = np.zeros((300, 400), dtype=np.uint8)

    h, w = wall_mask.shape[:2]

    walls: List[Dict[str, Any]] = []
    wall_lines = []
    wall_count = 0

    # 1 & 2. Wall contours & approxPolyDP
    contours, _ = cv2.findContours(wall_mask, cv2.RETR_LIST, cv2.CHAIN_APPROX_SIMPLE)
    for c in contours:
        perimeter = cv2.arcLength(c, True)
        if perimeter < 20:
            continue
        approx = cv2.approxPolyDP(c, 0.01 * perimeter, True)
        pts = approx.reshape(-1, 2)
        n = len(pts)
        for i in range(n):
            p1 = pts[i]
            p2 = pts[(i + 1) % n]
            length_px = math.hypot(p2[0] - p1[0], p2[1] - p1[1])
            if length_px < 5:  # filter tiny edges
                continue

            wall_count += 1
            wall_id = f"wall_b_{wall_count:03d}"

            start_m = [round(float(p1[0]) * default_mpp, 3), round(float(p1[1]) * default_mpp, 3)]
            end_m = [round(float(p2[0]) * default_mpp, 3), round(float(p2[1]) * default_mpp, 3)]

            walls.append({
                "id": wall_id,
                "start": start_m,
                "end": end_m,
                "thickness": DEFAULT_WALL_THICKNESS,
                "height": DEFAULT_WALL_HEIGHT,
                "source": "detected",
                "confidence": 0.50,
            })
            wall_lines.append((wall_id, (p1[0], p1[1]), (p2[0], p2[1])))

    # If no walls extracted from contour edges, fallback wall rectangle around mask bounds
    if not walls:
        walls = [
            {
                "id": "wall_b_001",
                "start": [0.0, 0.0],
                "end": [round(w * default_mpp, 3), 0.0],
                "thickness": DEFAULT_WALL_THICKNESS,
                "height": DEFAULT_WALL_HEIGHT,
                "source": "estimated",
                "confidence": 0.30,
            }
        ]
        wall_lines.append(("wall_b_001", (0, 0), (w, 0)))

    # 4. Doors via connected components attached to nearest wall with NO checks
    doors: List[Dict[str, Any]] = []
    door_count = 0
    if door_mask is not None and np.any(door_mask > 0):
        num_labels, labels, stats, centroids = cv2.connectedComponentsWithStats(door_mask)
        for i in range(1, num_labels):
            area = stats[i, cv2.CC_STAT_AREA]
            if area < 5:
                continue
            cx, cy = centroids[i]

            # Find nearest wall
            best_wall_id = walls[0]["id"]
            best_dist = float("inf")
            for w_id, wp1, wp2 in wall_lines:
                dist = point_to_segment_distance((cx, cy), wp1, wp2)
                if dist < best_dist:
                    best_dist = dist
                    best_wall_id = w_id

            door_count += 1
            doors.append({
                "id": f"door_b_{door_count:03d}",
                "wall_id": best_wall_id,
                "position": 0.50,
                "width": DEFAULT_DOOR_WIDTH,
                "height": DEFAULT_DOOR_HEIGHT,
                "source": "detected",
                "confidence": 0.50,
            })

    # Windows via connected components
    windows: List[Dict[str, Any]] = []
    win_count = 0
    if window_mask is not None and np.any(window_mask > 0):
        num_labels, labels, stats, centroids = cv2.connectedComponentsWithStats(window_mask)
        for i in range(1, num_labels):
            area = stats[i, cv2.CC_STAT_AREA]
            if area < 5:
                continue
            cx, cy = centroids[i]

            best_wall_id = walls[0]["id"]
            best_dist = float("inf")
            for w_id, wp1, wp2 in wall_lines:
                dist = point_to_segment_distance((cx, cy), wp1, wp2)
                if dist < best_dist:
                    best_dist = dist
                    best_wall_id = w_id

            win_count += 1
            windows.append({
                "id": f"window_b_{win_count:03d}",
                "wall_id": best_wall_id,
                "position": 0.50,
                "width": DEFAULT_WINDOW_HEIGHT,
                "sill_height": DEFAULT_WINDOW_SILL_HEIGHT,
                "height": DEFAULT_WINDOW_HEIGHT,
                "source": "detected",
                "confidence": 0.50,
            })

    # 5. Rooms via floor_mask contours
    rooms: List[Dict[str, Any]] = []
    room_count = 0
    if floor_mask is not None and np.any(floor_mask > 0):
        f_contours, _ = cv2.findContours(floor_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        for fc in f_contours:
            if cv2.contourArea(fc) < 50:
                continue
            approx_f = cv2.approxPolyDP(fc, 0.02 * cv2.arcLength(fc, True), True)
            pts_f = approx_f.reshape(-1, 2)
            if len(pts_f) >= 3:
                room_count += 1
                poly_m = [
                    [round(float(pt[0]) * default_mpp, 3), round(float(pt[1]) * default_mpp, 3)]
                    for pt in pts_f
                ]
                rooms.append({
                    "id": f"room_b_{room_count:03d}",
                    "polygon": poly_m,
                    "source": "detected",
                    "confidence": 0.50,
                })

    scene_dict = {
        "version": "1.0",
        "units": "meters",
        "source": {"filename": "baseline_input.png"},
        "scale": {
            "value": float(default_mpp),
            "unit": "meters_per_pixel",
            "source": "estimated",
            "confidence": 0.30,
        },
        "walls": walls,
        "doors": doors,
        "windows": windows,
        "rooms": rooms,
    }

    validate_against_schema(scene_dict)
    return scene_dict


def point_to_segment_distance(
    pt: Tuple[float, float],
    p1: Tuple[float, float],
    p2: Tuple[float, float]
) -> float:
    px, py = pt
    x1, y1 = p1
    x2, y2 = p2
    dx, dy = x2 - x1, y2 - y1
    if dx == 0 and dy == 0:
        return math.hypot(px - x1, py - y1)
    t = ((px - x1) * dx + (py - y1) * dy) / (dx * dx + dy * dy)
    t = max(0.0, min(1.0, t))
    proj_x = x1 + t * dx
    proj_y = y1 + t * dy
    return math.hypot(px - proj_x, py - proj_y)
