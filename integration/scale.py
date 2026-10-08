import re
import math
import logging
from pathlib import Path
from typing import Dict, Any, List, Tuple, Optional
import numpy as np
import cv2
from PIL import Image

from .config import (
    DEFAULT_ESTIMATED_MPP,
    DEFAULT_DOOR_WIDTH,
    SANITY_MIN_ROOM_WIDTH,
    SANITY_MAX_BUILDING_WIDTH,
    SANITY_MIN_WALL_THICKNESS,
    SANITY_MAX_WALL_THICKNESS,
    SANITY_MIN_DOOR_WIDTH,
    SANITY_MAX_DOOR_WIDTH,
)

log = logging.getLogger(__name__)

# Dimension text parsing regexes
REGEX_MM = re.compile(r"^(\d{3,5})\s*(?:mm)?$", re.IGNORECASE)
REGEX_M = re.compile(r"^(\d+(?:[\.,]\d+)?)\s*m$", re.IGNORECASE)
REGEX_FT_IN = re.compile(r"^(\d+)\s*['′]\s*(?:(\d+)\s*[\"″])?$", re.IGNORECASE)


def parse_dimension_text(text: str) -> Optional[float]:
    """
    Parse a text string into real-world length in meters.
    Examples:
    - "4500", "4500 mm" -> 4.5 m
    - "4.5 m", "4,5m", "450 cm" -> 4.5 m
    - "15'-0"", "12 ft", "15ft 0in" -> meters
    """
    text = text.strip()

    # Check mm (e.g., 4500, 4500 mm, 3200mm)
    m_mm = REGEX_MM.match(text)
    if m_mm:
        val = float(m_mm.group(1))
        if 500 <= val <= 30000:  # Realistic dimension in mm (0.5m to 30m)
            return val / 1000.0

    # Check meters (e.g. 4.5 m, 4,5m)
    m_m = REGEX_M.match(text.replace(",", "."))
    if m_m:
        val = float(m_m.group(1))
        if 0.5 <= val <= 50.0:
            return val

    # Check cm
    m_cm = re.match(r"^(\d+(?:[\.,]\d+)?)\s*cm$", text, re.IGNORECASE)
    if m_cm:
        val = float(m_cm.group(1).replace(",", "."))
        if 50 <= val <= 5000:
            return val / 100.0

    # Check feet/inches (e.g. 15'-0", 12 ft, 15ft, 15')
    m_ft = re.match(r"^(\d+)\s*(?:['′]|ft|feet)?\s*(?:-?\s*(\d+)\s*(?:[\"″]|in|inch|inches)?)?$", text, re.IGNORECASE)
    if m_ft:
        ft = float(m_ft.group(1))
        inches = float(m_ft.group(2)) if m_ft.group(2) else 0.0
        tot_ft = ft + inches / 12.0
        val_m = tot_ft * 0.3048
        if 0.5 <= val_m <= 50.0:
            return val_m

    if "ft" in text.lower() or "feet" in text.lower():
        parts = re.findall(r"\d+", text)
        if parts:
            return float(parts[0]) * 0.3048

    return None


def run_ocr_on_image(image_path: Path | str) -> List[Tuple[str, Tuple[float, float]]]:
    """Run OCR (EasyOCR fallback PyTesseract) and return list of (text, (center_x, center_y))."""
    results = []

    # Try EasyOCR
    try:
        import easyocr
        reader = easyocr.Reader(["en"], gpu=False)
        ocr_res = reader.readtext(str(image_path))
        for bbox, text, prob in ocr_res:
            if prob > 0.3:
                pts = np.array(bbox)
                cx, cy = float(np.mean(pts[:, 0])), float(np.mean(pts[:, 1]))
                results.append((text, (cx, cy)))
        if results:
            return results
    except Exception as e:
        log.debug("EasyOCR not available or failed: %s", e)

    # Fallback to PyTesseract
    try:
        import pytesseract
        img = Image.open(image_path)
        data = pytesseract.image_to_data(img, output_type=pytesseract.Output.DICT)
        n_boxes = len(data["text"])
        for i in range(n_boxes):
            text = data["text"][i].strip()
            conf = float(data["conf"][i])
            if text and conf > 30:
                x, y, w, h = data["left"][i], data["top"][i], data["width"][i], data["height"][i]
                cx, cy = float(x + w / 2.0), float(y + h / 2.0)
                results.append((text, (cx, cy)))
    except Exception as e:
        log.debug("PyTesseract not available or failed: %s", e)

    return results


def calibrate_scale(
    scene_px: Dict[str, Any],
    image_path: Optional[Path | str] = None
) -> Tuple[float, str, float, List[str]]:
    """
    Calibrate meters-per-pixel scale for the scene using Method A (Explicit OCR),
    Method B (Reference Door Width), or Method C (Estimated).
    Returns (mpp, source_type, confidence, warnings).
    """
    warnings = []

    # Method A: Explicit OCR dimension extraction
    if image_path and Path(image_path).exists():
        try:
            ocr_items = run_ocr_on_image(image_path)
            dim_pairs = []

            # Detect Hough line segments in image
            img_gray = cv2.imread(str(image_path), cv2.IMREAD_GRAYSCALE)
            if img_gray is not None:
                edges = cv2.Canny(img_gray, 50, 150)
                lines = cv2.HoughLinesP(edges, 1, np.pi / 180, threshold=50, minLineLength=30, maxLineGap=10)

                if lines is not None:
                    line_segs = [l[0] for l in lines]  # [x1, y1, x2, y2]
                    for text, (cx, cy) in ocr_items:
                        real_m = parse_dimension_text(text)
                        if real_m is None:
                            continue

                        # Find nearest line segment
                        best_len_px = None
                        min_dist = float("inf")
                        for x1, y1, x2, y2 in line_segs:
                            length_px = math.hypot(x2 - x1, y2 - y1)
                            if length_px < 10:
                                continue
                            mid_x, mid_y = (x1 + x2) / 2.0, (y1 + y2) / 2.0
                            dist = math.hypot(mid_x - cx, mid_y - cy)
                            if dist < min_dist and dist < 100:  # within 100px
                                min_dist = dist
                                best_len_px = length_px

                        if best_len_px:
                            mpp = real_m / best_len_px
                            if 0.001 <= mpp <= 0.2:  # Reasonable scale range
                                dim_pairs.append(mpp)

            if dim_pairs:
                median_mpp = float(np.median(dim_pairs))
                std_mpp = float(np.std(dim_pairs)) if len(dim_pairs) > 1 else 0.0
                spread_ratio = std_mpp / median_mpp if median_mpp > 0 else 0.0
                confidence = max(0.50, min(0.95, 0.90 - spread_ratio))

                log.info("Calibrated scale via Method A (Explicit OCR): %.5f m/px", median_mpp)
                return median_mpp, "explicit", confidence, warnings
        except Exception as e:
            log.debug("Method A scale calibration failed: %s", e)

    # Method B: Reference object (Doors)
    doors = scene_px.get("doors", [])
    door_widths_px = [d.get("width", 0.0) for d in doors if d.get("width", 0.0) > 0]
    if door_widths_px:
        med_door_px = float(np.median(door_widths_px))
        if med_door_px > 5.0:
            mpp = DEFAULT_DOOR_WIDTH / med_door_px  # 0.90 m / med_door_px
            conf = 0.70 if len(doors) >= 2 else 0.60
            log.info("Calibrated scale via Method B (Door Reference): %.5f m/px", mpp)
            return mpp, "reference", conf, warnings

    # Method C: Estimated default scale
    walls = scene_px.get("walls", [])
    wall_thicknesses = [w.get("thickness", 0.0) for w in walls if w.get("thickness", 0.0) > 0]
    if wall_thicknesses:
        med_th_px = float(np.median(wall_thicknesses))
        if med_th_px > 1.0:
            # Assume standard wall thickness ~0.20 m
            mpp = 0.20 / med_th_px
            log.info("Calibrated scale via Method C (Wall Thickness Heuristic): %.5f m/px", mpp)
            return mpp, "estimated", 0.45, warnings

    log.info("Calibrated scale via Method C (Default Fallback): %.5f m/px", DEFAULT_ESTIMATED_MPP)
    return DEFAULT_ESTIMATED_MPP, "estimated", 0.30, warnings


def apply_scale(
    scene_px: Dict[str, Any],
    mpp: float,
    scale_source: str = "estimated",
    confidence: float = 0.50
) -> Tuple[Dict[str, Any], List[str]]:
    """
    Apply scale factor to pixel coordinates, converting scene to meters.
    Normalizes coordinates so min bounds start near origin.
    Returns (scaled_scene_dict, warnings).
    """
    warnings = []
    scene_m = json_clone(scene_px)
    scene_m["units"] = "meters"
    scene_m["scale"] = {
        "value": float(mpp),
        "unit": "meters_per_pixel",
        "source": scale_source,
        "confidence": float(confidence),
    }

    # Gather min x and min y to normalize origin
    all_x = []
    all_y = []
    for wall in scene_m.get("walls", []):
        all_x.extend([wall["start"][0], wall["end"][0]])
        all_y.extend([wall["start"][1], wall["end"][1]])

    min_x = min(all_x) if all_x else 0.0
    min_y = min(all_y) if all_y else 0.0

    # Scale Walls
    for wall in scene_m.get("walls", []):
        wall["start"] = [
            round((wall["start"][0] - min_x) * mpp, 3),
            round((wall["start"][1] - min_y) * mpp, 3),
        ]
        wall["end"] = [
            round((wall["end"][0] - min_x) * mpp, 3),
            round((wall["end"][1] - min_y) * mpp, 3),
        ]
        wall["thickness"] = round(wall["thickness"] * mpp, 3)
        # Height is already in meters, default 3.0 if missing
        if "height" not in wall or wall["height"] <= 0:
            wall["height"] = 3.0

    # Scale Doors
    for door in scene_m.get("doors", []):
        door["width"] = round(door["width"] * mpp, 3)
        if "height" not in door or door["height"] <= 0:
            door["height"] = 2.10

    # Scale Windows
    for window in scene_m.get("windows", []):
        window["width"] = round(window["width"] * mpp, 3)
        if "sill_height" not in window or window["sill_height"] < 0:
            window["sill_height"] = 0.90
        if "height" not in window or window["height"] <= 0:
            window["height"] = 1.20

    # Scale Rooms
    for room in scene_m.get("rooms", []):
        scaled_poly = []
        for pt in room.get("polygon", []):
            scaled_poly.append([
                round((pt[0] - min_x) * mpp, 3),
                round((pt[1] - min_y) * mpp, 3),
            ])
        room["polygon"] = scaled_poly

    # Sanity checks on scaled parameters
    for room in scene_m.get("rooms", []):
        pts = np.array(room["polygon"])
        if len(pts) >= 3:
            w_box = float(np.ptp(pts[:, 0]))
            h_box = float(np.ptp(pts[:, 1]))
            if min(w_box, h_box) < SANITY_MIN_ROOM_WIDTH:
                warnings.append(f"Room {room['id']} is unusually small ({min(w_box, h_box):.2f} m)")

    building_w = max(all_x) - min_x if all_x else 0
    building_h = max(all_y) - min_y if all_y else 0
    if max(building_w * mpp, building_h * mpp) > SANITY_MAX_BUILDING_WIDTH:
        warnings.append(f"Unusually large building width ({max(building_w * mpp, building_h * mpp):.2f} m)")

    for wall in scene_m.get("walls", []):
        th = wall["thickness"]
        if not (SANITY_MIN_WALL_THICKNESS <= th <= SANITY_MAX_WALL_THICKNESS):
            warnings.append(f"Wall {wall['id']} has unusual thickness ({th:.2f} m)")

    for door in scene_m.get("doors", []):
        dw = door["width"]
        if not (SANITY_MIN_DOOR_WIDTH <= dw <= SANITY_MAX_DOOR_WIDTH):
            warnings.append(f"Door {door['id']} has unusual width ({dw:.2f} m)")

    if warnings and scale_source == "estimated":
        scene_m["scale"]["confidence"] = max(0.1, scene_m["scale"]["confidence"] - 0.15)

    return scene_m, warnings


def json_clone(data: Dict[str, Any]) -> Dict[str, Any]:
    import json
    return json.loads(json.dumps(data))
