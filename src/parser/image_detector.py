"""Computer vision pipeline for extracting architectural walls, rooms, and openings from floor plan images."""

from __future__ import annotations

import math
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

import cv2
import numpy as np

from src.config import CONFIG
from src.geometry.binding import OpeningBinder, RawOpening
from src.geometry.merging import CollinearWallMerger
from src.geometry.rooms import RoomTopologyEngine
from src.geometry.snapping import SnappingEngine
from src.models import (
    FloorPlan,
    OpeningType,
    Point2D,
    RoomPolygon,
    ValidationLevel,
    ValidationReport,
    WallEdge,
)


class BlueprintImageDetector:
    """
    Extracts structural geometry from raster floor plans (PNG, JPG):
    1. Adaptive filtering and morphological wall separation
    2. Hough line vectorization and endpoint clustering
    3. Scale bar detection / scale calibration
    4. Door swing arc and window opening classification
    5. Room polygonization
    """

    def __init__(self, default_scale_m_per_px: float = 0.02) -> None:
        self.default_scale = default_scale_m_per_px

    def detect_scale_bar(self, img_gray: np.ndarray) -> Optional[float]:
        """
        Scans bottom region of image to detect standard CAD metric scale bar.
        Returns estimated scale in meters per pixel if found.
        """
        scale, _ = self.detect_scale_bar_info(img_gray)
        return scale

    def detect_scale_bar_info(
        self, img_gray: np.ndarray
    ) -> Tuple[Optional[float], Optional[Tuple[int, int, int, int]]]:
        """
        Scans bottom region of image to detect standard CAD metric scale bar.
        Returns (estimated scale in meters per pixel, scale bar bbox (x1, y1, x2, y2)) if found.
        """
        h, w = img_gray.shape
        # Search bottom 25% of image
        crop_y = int(h * 0.75)
        roi = img_gray[crop_y:h, :]

        # Binary threshold
        _, bin_roi = cv2.threshold(roi, 100, 255, cv2.THRESH_BINARY_INV)

        # Detect horizontal lines with morphological kernel
        kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (40, 1))
        horiz = cv2.morphologyEx(bin_roi, cv2.MORPH_OPEN, kernel)

        lines = cv2.HoughLinesP(horiz, 1, np.pi / 180, threshold=50, minLineLength=100, maxLineGap=10)
        if lines is not None and len(lines) > 0:
            longest_len = 0.0
            best_bbox: Optional[Tuple[int, int, int, int]] = None
            for line in lines:
                coords = line.reshape(-1)
                x1, y1, x2, y2 = int(coords[0]), int(coords[1]), int(coords[2]), int(coords[3])
                length = float(math.hypot(x2 - x1, y2 - y1))
                if length >= 100:
                    abs_y = y1 + crop_y
                    if abs_y - 25 >= 0:
                        min_x, max_x = min(x1, x2), max(x1, x2)
                        if max_x > min_x:
                            above_slice = img_gray[max(0, abs_y - 25) : max(0, abs_y - 5), min_x:max_x]
                            below_slice = img_gray[min(h, abs_y + 5) : min(h, abs_y + 25), min_x:max_x]
                            dark_above = np.count_nonzero(above_slice < 150)
                            dark_below = np.count_nonzero(below_slice < 150)
                            density_above = dark_above / above_slice.size if above_slice.size > 0 else 0
                            density_below = dark_below / below_slice.size if below_slice.size > 0 else 0
                            # A real scale bar sits in empty canvas margin
                            if density_above > 0.06 or density_below > 0.20:
                                continue

                    if length > longest_len:
                        longest_len = length
                        best_bbox = (min(x1, x2), abs_y - 12, max(x1, x2), abs_y + 12)

            if longest_len >= 100 and best_bbox is not None:
                # Standard 5m CAD scale bar
                scale = 5.0 / longest_len
                return scale, best_bbox


        return None, None

    def detect_features(
        self,
        img_gray: np.ndarray,
        initial_scale: Optional[float] = None,
        scale_bar_roi: Optional[Tuple[int, int, int, int]] = None,
    ) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]], np.ndarray, List[np.ndarray], float]:
        """
        Extracts door arcs, wall apertures (cutouts), classifies doors vs windows,
        and constructs a clean solid wall mask.
        Returns: (doors_data, windows_data, wall_solid, room_contours, effective_scale)
        """
        img_h, img_w = img_gray.shape[:2]
        _, thresh = cv2.threshold(img_gray, 200, 255, cv2.THRESH_BINARY_INV)

        wall_solid = thresh.copy()

        # Erase detected scale bar from wall_solid so it is not vectorized as an architectural wall
        if scale_bar_roi is not None:
            bx1, by1, bx2, by2 = scale_bar_roi
            y1_clamped = max(0, by1 - 8)
            y2_clamped = min(img_h, by2 + 25)
            x1_clamped = max(0, bx1 - 20)
            x2_clamped = min(img_w, bx2 + 20)
            wall_solid[y1_clamped:y2_clamped, x1_clamped:x2_clamped] = 0

        # Clear canvas boundary margins (4px) to suppress scanning/crop border frame lines
        margin = 4
        wall_solid[:margin, :] = 0
        wall_solid[-margin:, :] = 0
        wall_solid[:, :margin] = 0
        wall_solid[:, -margin:] = 0

        contours_tree, hier_tree = cv2.findContours(thresh, cv2.RETR_TREE, cv2.CHAIN_APPROX_SIMPLE)

        door_arcs: List[Tuple[int, int, int, int]] = []
        raw_apertures: List[Tuple[int, int, int, int]] = []
        room_contours: List[np.ndarray] = []

        total_img_area = img_h * img_w
        dim_min, dim_max = min(img_h, img_w), max(img_h, img_w)

        # 1. Enclosed hierarchy classification (robust for architectural CAD & raster plans across any image resolution)
        if hier_tree is not None and len(contours_tree) > 0:
            building_parents = {
                i
                for i, c in enumerate(contours_tree)
                if hier_tree[0][i][3] == -1 and cv2.contourArea(c) > 0.05 * total_img_area
            }
            if not building_parents:
                root_indices = [i for i, c in enumerate(contours_tree) if hier_tree[0][i][3] == -1]
                if root_indices:
                    largest_root = max(root_indices, key=lambda idx: cv2.contourArea(contours_tree[idx]))
                    building_parents.add(largest_root)
                else:
                    building_parents.add(0)

            for i, c in enumerate(contours_tree):
                parent = hier_tree[0][i][3]
                if parent in building_parents:
                    area = cv2.contourArea(c)
                    bx, by, bw, bh = cv2.boundingRect(c)
                    aspect = min(bw, bh) / max(bw, bh) if max(bw, bh) > 0 else 0.0
                    fill = area / (bw * bh) if bw * bh > 0 else 0.0
                    min_side = min(bw, bh)
                    area_ratio = area / total_img_area

                    # Check Door Arc first:
                    # Quarter circle sector has aspect >= 0.60, fill ~0.65 to 0.86,
                    # and opening width between 2% and 15% of image dimension.
                    is_door_arc = (
                        aspect >= 0.60
                        and 0.65 <= fill <= 0.86
                        and (0.020 * dim_min) <= min_side <= (0.15 * dim_max)
                        and 0.0008 <= area_ratio <= 0.020
                    )

                    if is_door_arc:
                        door_arcs.append((bx, by, bw, bh))
                        # Erase door arc interior and perimeter stroke lines from solid wall mask
                        cv2.drawContours(wall_solid, [c], -1, 0, -1)
                        cv2.drawContours(wall_solid, [c], -1, 0, thickness=9)
                    elif area_ratio >= 0.008 and area > 1000:
                        room_contours.append(c)
                    elif 60 < area < (0.035 * total_img_area):
                        raw_apertures.append((bx, by, bw, bh))
                        # Fill wall aperture in solid wall mask
                        cv2.drawContours(wall_solid, [c], -1, 255, -1)

        # 2. Open circular arc fallback (for thin-line CAD vector blueprints where arcs are not filled sectors)
        contours_list, _ = cv2.findContours(thresh, cv2.RETR_LIST, cv2.CHAIN_APPROX_SIMPLE)
        scale_for_arc = initial_scale if initial_scale and initial_scale > 0 else 0.02
        for c in contours_list:
            peri = cv2.arcLength(c, False)
            if peri > 30:
                (cx, cy), radius = cv2.minEnclosingCircle(c)
                radius_m = radius * scale_for_arc
                if 0.50 <= radius_m <= 1.45:
                    bx, by, bw, bh = cv2.boundingRect(c)
                    already = any(
                        abs(cx - (dx + dw / 2.0)) < max(dw, dh) * 0.9
                        and abs(cy - (dy + dh / 2.0)) < max(dw, dh) * 0.9
                        for dx, dy, dw, dh in door_arcs
                    )
                    if not already:
                        door_arcs.append((bx, by, bw, bh))
                        cv2.drawContours(wall_solid, [c], -1, 0, thickness=9)

        # Deduplicate apertures that significantly overlap (Non-Maximum Suppression)
        apertures: List[Tuple[int, int, int, int]] = []
        for ax, ay, aw, ah in raw_apertures:
            acx, acy = ax + aw / 2.0, ay + ah / 2.0
            is_dup = False
            for cax, cay, caw, cah in apertures:
                cacx, cacy = cax + caw / 2.0, cay + cah / 2.0
                if math.hypot(acx - cacx, acy - cacy) < 0.35 * max(aw, ah, caw, cah):
                    is_dup = True
                    break
            if not is_dup:
                apertures.append((ax, ay, aw, ah))

        # 3. Classify apertures as DOOR or WINDOW based on proximity to door arcs
        doors_data: List[Dict[str, Any]] = []
        windows_data: List[Dict[str, Any]] = []
        door_lens: List[float] = []

        for ax, ay, aw, ah in apertures:
            acx, acy = ax + aw / 2.0, ay + ah / 2.0
            alen = max(aw, ah)
            is_door = False
            for dx, dy, dw, dh in door_arcs:
                dcx, dcy = dx + dw / 2.0, dy + dh / 2.0
                if math.hypot(acx - dcx, acy - dcy) < max(dw, dh) * 1.35:
                    is_door = True
                    break
            if is_door:
                doors_data.append({
                    "center_px": (acx, acy),
                    "width_px": alen,
                    "bbox": (ax, ay, aw, ah),
                    "confidence": 0.90,
                    "uncertain": False,
                    "detection_type": "aperture_with_arc",
                })
                door_lens.append(alen)
            else:
                windows_data.append({
                    "center_px": (acx, acy),
                    "width_px": alen,
                    "bbox": (ax, ay, aw, ah),
                    "confidence": 0.85,
                    "uncertain": False,
                    "detection_type": "aperture",
                })

        # 4. If any door arcs had no enclosed wall aperture, create a door opening at the arc hinge
        for dx, dy, dw, dh in door_arcs:
            dcx, dcy = dx + dw / 2.0, dy + dh / 2.0
            dlen = max(dw, dh)
            has_ap = any(
                math.hypot(dcx - d["center_px"][0], dcy - d["center_px"][1]) < dlen * 1.35
                for d in doors_data
            )
            if not has_ap:
                doors_data.append({
                    "center_px": (dcx, dcy),
                    "width_px": dlen,
                    "bbox": (dx, dy, dw, dh),
                    "confidence": 0.70,
                    "uncertain": True,
                    "uncertainty_reason": "Inferred door opening from swing arc without explicit wall aperture",
                    "detection_type": "arc_inferred",
                })
                door_lens.append(dlen)

        # 5. Scale calibration: Estimate from median door width (standard residential door = 0.90m)
        if initial_scale and initial_scale > 0:
            effective_scale = initial_scale
        elif door_lens:
            median_door_px = float(np.median(door_lens))
            if median_door_px > 5.0:
                cal_scale = 0.90 / median_door_px
                if 0.003 <= cal_scale <= 0.15:
                    effective_scale = cal_scale
                else:
                    effective_scale = self.default_scale
            else:
                effective_scale = self.default_scale
        else:
            effective_scale = self.default_scale

        return doors_data, windows_data, wall_solid, room_contours, effective_scale

    def extract_skeleton_walls(
        self, wall_solid: np.ndarray, scale: float, img_h: int
    ) -> List[WallEdge]:
        """
        Morphological skeletonization preserving centerlines of ALL walls:
        orthogonal (0°, 90°) AND free-form angled/diagonal walls.
        """
        # Distance transform cleanup: strip any thin drafting lines (symbols, dimension lines, door arcs)
        dist = cv2.distanceTransform(wall_solid, cv2.DIST_L2, 5)
        if dist.max() > 4.0:
            clean_solid = np.zeros_like(wall_solid)
            clean_solid[dist > 2.2] = 255
            clean_solid = cv2.dilate(clean_solid, cv2.getStructuringElement(cv2.MORPH_CROSS, (5, 5)))
            wall_solid = cv2.bitwise_and(clean_solid, wall_solid)

        skel = np.zeros(wall_solid.shape, np.uint8)
        element = cv2.getStructuringElement(cv2.MORPH_CROSS, (3, 3))
        temp = wall_solid.copy()

        while cv2.countNonZero(temp) > 0:
            eroded = cv2.erode(temp, element)
            temp2 = cv2.dilate(eroded, element)
            temp2 = cv2.subtract(temp, temp2)
            skel = cv2.bitwise_or(skel, temp2)
            temp = eroded.copy()

        # Vectorize skeleton into line centerlines
        min_line_len = max(15, int(0.25 / scale))
        max_gap = max(10, int(0.30 / scale))

        lines = cv2.HoughLinesP(
            skel,
            rho=1,
            theta=np.pi / 180,
            threshold=18,
            minLineLength=min_line_len,
            maxLineGap=max_gap,
        )

        raw_walls: List[WallEdge] = []
        if lines is None:
            return raw_walls

        img_w = wall_solid.shape[1]
        border_margin = 6

        for idx, line in enumerate(lines):
            coords = line.reshape(-1)
            x1, y1, x2, y2 = coords[0], coords[1], coords[2], coords[3]

            # Filter out lines that lie along the extreme canvas borders (scan/crop margins)
            if (x1 < border_margin and x2 < border_margin) or (x1 > img_w - border_margin and x2 > img_w - border_margin):
                continue
            if (y1 < border_margin and y2 < border_margin) or (y1 > img_h - border_margin and y2 > img_h - border_margin):
                continue

            p1 = Point2D(x1 * scale, (img_h - y1) * scale)
            p2 = Point2D(x2 * scale, (img_h - y2) * scale)

            # Snap very near horizontal or very near vertical lines (< 3 degrees)
            dx = abs(p2.x - p1.x)
            dy = abs(p2.y - p1.y)
            if dx > 0 and dy > 0:
                angle_deg = math.degrees(math.atan2(min(dx, dy), max(dx, dy)))
                if angle_deg < 2.5:
                    if dx > dy:
                        avg_y = 0.5 * (p1.y + p2.y)
                        p1 = Point2D(p1.x, avg_y)
                        p2 = Point2D(p2.x, avg_y)
                    else:
                        avg_x = 0.5 * (p1.x + p2.x)
                        p1 = Point2D(avg_x, p1.y)
                        p2 = Point2D(avg_x, p2.y)

            if p1.distance_to(p2) >= CONFIG.MIN_WALL_LENGTH:
                raw_walls.append(
                    WallEdge(
                        id=f"cv_wall_{idx + 1}",
                        start=p1,
                        end=p2,
                        thickness=CONFIG.WALL_THICKNESS,
                        height=CONFIG.WALL_HEIGHT,
                    )
                )

        return raw_walls

    def parse_image(
        self,
        image_path: Union[str, Path],
        scale: Optional[float] = None,
        report: Optional[ValidationReport] = None,
    ) -> FloorPlan:
        """Runs the complete CV extraction pipeline on the input blueprint image."""
        if report is None:
            report = ValidationReport()

        path = Path(image_path)
        img = cv2.imread(str(path))
        if img is None:
            report.add(ValidationLevel.ERROR, "IMAGE_LOAD_FAILED", f"Could not read image from {path}")
            return FloorPlan(validation=report)

        img_h, img_w = img.shape[:2]
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

        # 1. Feature Extraction (Doors, Windows, Solid Wall Mask, and Room Cavities)
        user_scale = scale if scale and scale > 0 else None
        scale_bar, scale_bar_roi = self.detect_scale_bar_info(gray)

        initial_scale = user_scale or scale_bar

        doors_data, windows_data, wall_solid, mask_rooms, effective_scale = self.detect_features(
            gray, initial_scale=initial_scale, scale_bar_roi=scale_bar_roi
        )

        scale_source = "default_fallback"
        scale_confidence = 0.50

        if user_scale is not None:
            effective_scale = user_scale
            scale_source = "user_specified"
            scale_confidence = 1.0
            report.add(
                ValidationLevel.INFO,
                "USER_SCALE_APPLIED",
                f"Using user-specified scale calibration: {effective_scale:.5f} m/pixel.",
            )
        elif scale_bar is not None and (0.002 <= scale_bar <= 0.20):
            # Cross-validate scale bar against detected door widths if doors were found
            is_valid_scale_bar = True
            if doors_data:
                median_door_px = float(np.median([d["width_px"] for d in doors_data]))
                implied_door_w = median_door_px * scale_bar
                if implied_door_w < 0.50 or implied_door_w > 1.60:
                    is_valid_scale_bar = False
                    report.add(
                        ValidationLevel.INFO,
                        "SCALE_BAR_REJECTED",
                        f"Detected line is not a valid 5m scale bar (implied door width {implied_door_w:.2f}m is unphysical). Falling back to door calibration.",
                    )

            if is_valid_scale_bar:
                effective_scale = scale_bar
                scale_source = "scale_bar"
                scale_confidence = 0.95
                report.add(
                    ValidationLevel.INFO,
                    "SCALE_BAR_DETECTED",
                    f"Auto-calibrated scale from detected CAD scale bar: {effective_scale:.5f} m/pixel.",
                )
            elif doors_data:
                median_door_px = float(np.median([d["width_px"] for d in doors_data]))
                effective_scale = 0.90 / median_door_px
                scale_source = "door_median"
                scale_confidence = 0.80
                report.add(
                    ValidationLevel.INFO,
                    "DOOR_SCALE_CALIBRATED",
                    f"Auto-calibrated scale from {len(doors_data)} detected doors (0.90m standard): {effective_scale:.5f} m/pixel.",
                )
        elif doors_data:
            scale_source = "door_median"
            scale_confidence = 0.80
            report.add(
                ValidationLevel.INFO,
                "DOOR_SCALE_CALIBRATED",
                f"Auto-calibrated scale from {len(doors_data)} detected doors (0.90m standard): {effective_scale:.5f} m/pixel.",
            )
        else:
            report.add(
                ValidationLevel.WARNING,
                "DEFAULT_SCALE_FALLBACK",
                f"No scale bar or doors found. Fallback default: {effective_scale:.5f} m/pixel.",
            )

        report.add(
            ValidationLevel.INFO,
            "CV_FEATURES_DETECTED",
            f"Detected {len(doors_data)} doors and {len(windows_data)} windows from blueprint apertures.",
        )

        # 3. Extract all-angle walls from skeleton
        raw_walls = self.extract_skeleton_walls(wall_solid, effective_scale, img_h)

        report.add(
            ValidationLevel.INFO,
            "CV_WALLS_EXTRACTED",
            f"Extracted {len(raw_walls)} raw linear wall segments from skeleton network.",
        )

        # 4. Geometry cleanup: Snapping and Collinear Merging
        snapper = SnappingEngine(tolerance=CONFIG.SNAP_TOLERANCE_METERS)
        merger = CollinearWallMerger(max_angle_deg=8.0, max_offset=0.25)

        snapped_walls = snapper.clean_and_snap(raw_walls, report=report)
        merged_walls = merger.merge_all(snapped_walls, report=report)
        final_walls = snapper.clean_and_snap(merged_walls, report=report)

        # 5. Bind Doors and Windows to host walls
        raw_openings: List[RawOpening] = []
        for idx, d in enumerate(doors_data):
            cx, cy = d["center_px"]
            pos = Point2D(cx * effective_scale, (img_h - cy) * effective_scale)
            width = d["width_px"] * effective_scale
            meta = dict(d)
            if width < 0.60 or width > 2.0:
                meta["uncertain"] = True
                meta["uncertainty_reason"] = f"Door aperture width ({width:.2f}m) outside typical residential range (0.60-2.00m)"
                meta["confidence"] = min(meta.get("confidence", 0.90), 0.60)
            raw_openings.append(
                RawOpening(
                    position=pos,
                    width=width,
                    opening_type=OpeningType.DOOR,
                    id=f"cv_door_{idx + 1}",
                    metadata=meta,
                )
            )

        for idx, w_item in enumerate(windows_data):
            cx, cy = w_item["center_px"]
            pos = Point2D(cx * effective_scale, (img_h - cy) * effective_scale)
            width = w_item["width_px"] * effective_scale
            meta = dict(w_item)
            if width < 0.35 or width > 3.5:
                meta["uncertain"] = True
                meta["uncertainty_reason"] = f"Window aperture width ({width:.2f}m) outside typical residential range (0.35-3.50m)"
                meta["confidence"] = min(meta.get("confidence", 0.85), 0.60)
            raw_openings.append(
                RawOpening(
                    position=pos,
                    width=width,
                    opening_type=OpeningType.WINDOW,
                    id=f"cv_window_{idx + 1}",
                    metadata=meta,
                )
            )

        binder = OpeningBinder(max_projection_distance=0.45)
        bound_count, unbound_count = binder.bind_openings(raw_openings, final_walls, report=report)

        # 6. Room topology extraction & polygon validation
        room_engine = RoomTopologyEngine(min_room_area=1.0)
        topological_rooms = room_engine.extract_rooms_from_walls(final_walls, report=report)

        # Process and clean mask rooms
        cleaned_mask_rooms: List[RoomPolygon] = []
        for idx, c in enumerate(mask_rooms):
            peri = cv2.arcLength(c, True)
            approx = cv2.approxPolyDP(c, 0.012 * peri, True)
            pts = [Point2D(p[0][0] * effective_scale, (img_h - p[0][1]) * effective_scale) for p in approx]

            cleaned_pts = room_engine.validate_and_clean_polygon(pts, report=None, room_id=f"mask_room_{idx + 1}")
            if cleaned_pts is not None and len(cleaned_pts) >= 3:
                # Check if raw polygon was self-intersecting
                raw_coords = [p.as_tuple() for p in pts]
                if raw_coords[0] != raw_coords[-1]:
                    raw_coords.append(raw_coords[0])
                from shapely.geometry import Polygon as ShapelyPoly
                is_repaired = not ShapelyPoly(raw_coords).is_valid

                room_meta = {
                    "source": "mask_cavity",
                    "confidence": 0.70 if is_repaired else 0.85,
                    "uncertain": is_repaired,
                }
                if is_repaired:
                    room_meta["uncertainty_reason"] = "Repaired self-intersecting boundary polygon from raster contour"

                cleaned_mask_rooms.append(
                    RoomPolygon(
                        id=f"room_{idx + 1}",
                        name=f"Room {idx + 1}",
                        points=cleaned_pts,
                        metadata=room_meta,
                    )
                )

        if len(topological_rooms) == 0:
            rooms = cleaned_mask_rooms
            if cleaned_mask_rooms:
                report.add(
                    ValidationLevel.INFO,
                    "ROOMS_FROM_MASK",
                    f"Recovered {len(cleaned_mask_rooms)} clean enclosed room polygons directly from solid wall cavities.",
                )
        elif len(cleaned_mask_rooms) > len(topological_rooms):
            rooms = list(topological_rooms)
            aug_count = 0
            for mr in cleaned_mask_rooms:
                mr_poly = mr.shapely_polygon
                if not mr_poly.is_valid or mr_poly.is_empty:
                    continue
                overlaps = any(
                    (mr_poly.intersection(tr.shapely_polygon).area / min(mr_poly.area, tr.shapely_polygon.area)) > 0.40
                    for tr in topological_rooms
                    if tr.shapely_polygon.is_valid and not tr.shapely_polygon.is_empty
                )
                if not overlaps:
                    mr.id = f"room_{len(rooms) + 1}"
                    mr.name = f"Room {len(rooms) + 1}"
                    rooms.append(mr)
                    aug_count += 1
            if aug_count > 0:
                report.add(
                    ValidationLevel.INFO,
                    "ROOMS_AUGMENTED_FROM_MASK",
                    f"Augmented {aug_count} clean room polygons from wall cavities alongside {len(topological_rooms)} topological rooms.",
                )
        else:
            rooms = topological_rooms

        # Collect uncertain detections
        uncertain_openings = []
        for w in final_walls:
            for op in w.openings:
                if op.metadata.get("uncertain", False):
                    uncertain_openings.append({
                        "id": op.id,
                        "type": op.opening_type.value,
                        "wall_id": w.id,
                        "width_m": round(op.width, 3),
                        "confidence": op.metadata.get("confidence", 0.7),
                        "reason": op.metadata.get("uncertainty_reason", "Unusual opening dimension or inferred without aperture"),
                    })

        uncertain_rooms = [
            {
                "id": r.id,
                "name": r.name,
                "area_sq_m": round(r.area, 3),
                "confidence": r.metadata.get("confidence", 0.7),
                "reason": r.metadata.get("uncertainty_reason", "Boundary repaired from mask cavity"),
            }
            for r in rooms
            if r.metadata.get("uncertain", False)
        ]

        uncertain_detections = {
            "scale": {
                "value_m_per_px": round(effective_scale, 6),
                "source": scale_source,
                "confidence": scale_confidence,
                "uncertain": scale_confidence < 0.80,
            },
            "openings": uncertain_openings,
            "rooms": uncertain_rooms,
            "unbound_openings_count": unbound_count,
        }

        if uncertain_openings or uncertain_rooms or scale_confidence < 0.80:
            report.add(
                ValidationLevel.INFO,
                "UNCERTAIN_DETECTIONS_DOCUMENTED",
                f"Documented {len(uncertain_openings)} uncertain openings, {len(uncertain_rooms)} uncertain rooms, scale confidence: {scale_confidence:.2f}.",
            )

        metadata = {
            "source": str(path),
            "image_width_px": img_w,
            "image_height_px": img_h,
            "bound_openings": bound_count,
            "doors_detected": len(doors_data),
            "windows_detected": len(windows_data),
            "uncertain_detections": uncertain_detections,
        }

        floor_plan = FloorPlan(
            walls=final_walls,
            rooms=rooms,
            scale=effective_scale,
            validation=report,
            metadata=metadata,
        )

        return floor_plan
