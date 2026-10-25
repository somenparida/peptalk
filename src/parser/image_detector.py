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
        h, w = img_gray.shape
        # Search bottom 20% of image
        crop_y = int(h * 0.80)
        roi = img_gray[crop_y:h, :]

        # Binary threshold
        _, bin_roi = cv2.threshold(roi, 100, 255, cv2.THRESH_BINARY_INV)

        # Detect horizontal lines with morphological kernel
        kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (40, 1))
        horiz = cv2.morphologyEx(bin_roi, cv2.MORPH_OPEN, kernel)

        lines = cv2.HoughLinesP(horiz, 1, np.pi / 180, threshold=50, minLineLength=100, maxLineGap=10)
        if lines is not None and len(lines) > 0:
            # Find longest isolated line in scale bar region
            longest_len = 0.0
            for line in lines:
                coords = line.reshape(-1)
                x1, y1, x2, y2 = coords[0], coords[1], coords[2], coords[3]
                length = float(math.hypot(x2 - x1, y2 - y1))
                if length >= 100:
                    # Check isolation: a real CAD scale bar sits in the bottom margin,
                    # separated from building walls above it by empty canvas.
                    abs_y = y1 + crop_y
                    if abs_y - 25 >= 0:
                        min_x, max_x = min(x1, x2), max(x1, x2)
                        above_slice = img_gray[abs_y - 25 : abs_y - 5, min_x:max_x]
                        dark_pixels_above = np.count_nonzero(above_slice < 150)
                        total_pixels = above_slice.size
                        density_above = dark_pixels_above / total_pixels if total_pixels > 0 else 0
                        if density_above > 0.05:
                            # Attached to or inside building walls, not an isolated scale bar
                            continue

                    if length > longest_len:
                        longest_len = length

            if longest_len >= 100:
                # Standard 5m CAD scale bar
                return 5.0 / longest_len

        return None

    def detect_features(
        self, img_gray: np.ndarray, initial_scale: Optional[float] = None
    ) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]], np.ndarray, List[np.ndarray], float]:
        """
        Extracts door arcs, wall apertures (cutouts), classifies doors vs windows,
        and constructs a clean solid wall mask.
        Returns: (doors_data, windows_data, wall_solid, room_contours, effective_scale)
        """
        img_h, img_w = img_gray.shape[:2]
        _, thresh = cv2.threshold(img_gray, 200, 255, cv2.THRESH_BINARY_INV)

        contours_tree, hier_tree = cv2.findContours(thresh, cv2.RETR_TREE, cv2.CHAIN_APPROX_SIMPLE)

        door_arcs: List[Tuple[int, int, int, int]] = []
        apertures: List[Tuple[int, int, int, int]] = []
        room_contours: List[np.ndarray] = []

        wall_solid = thresh.copy()

        total_img_area = img_h * img_w
        dim_min, dim_max = min(img_h, img_w), max(img_h, img_w)

        # 1. Enclosed hierarchy classification (robust for architectural CAD & raster plans across any image resolution)
        if hier_tree is not None and len(contours_tree) > 0:
            # Dynamically identify the main building wall outline contours (large root contours)
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
                    # Quarter circle sector has aspect >= 0.65, fill ~0.70 to 0.83 (pi/4 = 0.785),
                    # and opening width between 2.5% and 12% of image dimension.
                    is_door_arc = (
                        aspect >= 0.65
                        and 0.68 <= fill <= 0.84
                        and (0.025 * dim_min) <= min_side <= (0.12 * dim_max)
                        and 0.001 <= area_ratio <= 0.015
                    )

                    if is_door_arc:
                        door_arcs.append((bx, by, bw, bh))
                        # Erase door arc interior and perimeter stroke lines from solid wall mask
                        cv2.drawContours(wall_solid, [c], -1, 0, -1)
                        cv2.drawContours(wall_solid, [c], -1, 0, thickness=9)
                    elif area_ratio >= 0.008 and area > 1000:
                        room_contours.append(c)
                    elif 80 < area < (0.025 * total_img_area):
                        apertures.append((bx, by, bw, bh))
                        # Fill wall aperture in solid wall mask
                        cv2.drawContours(wall_solid, [c], -1, 255, -1)

        # 2. Open circular arc fallback (for thin-line CAD vector blueprints where arcs are not filled sectors)
        if len(door_arcs) == 0:
            contours_list, _ = cv2.findContours(thresh, cv2.RETR_LIST, cv2.CHAIN_APPROX_SIMPLE)
            scale_for_arc = initial_scale if initial_scale and initial_scale > 0 else 0.02
            for c in contours_list:
                peri = cv2.arcLength(c, False)
                if peri > 35:
                    (cx, cy), radius = cv2.minEnclosingCircle(c)
                    radius_m = radius * scale_for_arc
                    if 0.60 <= radius_m <= 1.30:
                        bx, by, bw, bh = cv2.boundingRect(c)
                        already = any(
                            abs(cx - (dx + dw / 2.0)) < dw and abs(cy - (dy + dh / 2.0)) < dh
                            for dx, dy, dw, dh in door_arcs
                        )
                        if not already:
                            door_arcs.append((bx, by, bw, bh))

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
                doors_data.append({"center_px": (acx, acy), "width_px": alen, "bbox": (ax, ay, aw, ah)})
                door_lens.append(alen)
            else:
                windows_data.append({"center_px": (acx, acy), "width_px": alen, "bbox": (ax, ay, aw, ah)})

        # 4. If any door arcs had no enclosed wall aperture, create a door opening at the arc hinge
        for dx, dy, dw, dh in door_arcs:
            dcx, dcy = dx + dw / 2.0, dy + dh / 2.0
            dlen = max(dw, dh)
            has_ap = any(
                math.hypot(dcx - d["center_px"][0], dcy - d["center_px"][1]) < dlen * 1.35
                for d in doors_data
            )
            if not has_ap:
                doors_data.append({"center_px": (dcx, dcy), "width_px": dlen, "bbox": (dx, dy, dw, dh)})
                door_lens.append(dlen)

        # 5. Scale calibration: Estimate from median door width (standard residential door = 0.90m)
        if initial_scale and initial_scale > 0:
            effective_scale = initial_scale
        elif door_lens:
            median_door_px = float(np.median(door_lens))
            effective_scale = 0.90 / median_door_px
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

        for idx, line in enumerate(lines):
            coords = line.reshape(-1)
            x1, y1, x2, y2 = coords[0], coords[1], coords[2], coords[3]

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
        # Explicit user scale takes precedence if provided; otherwise auto-calibrates from doors.
        user_scale = scale if scale and scale > 0 else None
        doors_data, windows_data, wall_solid, mask_rooms, effective_scale = self.detect_features(
            gray, initial_scale=user_scale
        )

        scale_bar = None
        if user_scale is not None:
            report.add(
                ValidationLevel.INFO,
                "USER_SCALE_APPLIED",
                f"Using user-specified scale calibration: {effective_scale:.5f} m/pixel.",
            )
        elif doors_data:
            report.add(
                ValidationLevel.INFO,
                "DOOR_SCALE_CALIBRATED",
                f"Auto-calibrated scale from {len(doors_data)} detected doors (0.90m standard): {effective_scale:.5f} m/pixel.",
            )
        else:
            scale_bar = self.detect_scale_bar(gray)
            if scale_bar is not None:
                effective_scale = scale_bar
                report.add(
                    ValidationLevel.INFO,
                    "SCALE_BAR_DETECTED",
                    f"Detected scale bar in blueprint: {effective_scale:.5f} m/pixel.",
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
            raw_openings.append(
                RawOpening(
                    position=pos,
                    width=width,
                    opening_type=OpeningType.DOOR,
                    id=f"cv_door_{idx + 1}",
                )
            )

        for idx, w_item in enumerate(windows_data):
            cx, cy = w_item["center_px"]
            pos = Point2D(cx * effective_scale, (img_h - cy) * effective_scale)
            width = w_item["width_px"] * effective_scale
            raw_openings.append(
                RawOpening(
                    position=pos,
                    width=width,
                    opening_type=OpeningType.WINDOW,
                    id=f"cv_window_{idx + 1}",
                )
            )

        binder = OpeningBinder(max_projection_distance=0.45)
        bound_count, unbound_count = binder.bind_openings(raw_openings, final_walls, report=report)

        # 6. Room topology extraction
        room_engine = RoomTopologyEngine()
        rooms = room_engine.extract_rooms_from_walls(final_walls, report=report)

        # If topological polygonization found fewer rooms than solid wall mask cavities, augment with mask rooms
        if len(rooms) < len(mask_rooms) and len(mask_rooms) > 0:
            report.add(
                ValidationLevel.INFO,
                "ROOMS_AUGMENTED_FROM_MASK",
                f"Recovered {len(mask_rooms)} clean enclosed room polygons directly from solid wall cavities.",
            )
            rooms = []
            for idx, c in enumerate(mask_rooms):
                peri = cv2.arcLength(c, True)
                approx = cv2.approxPolyDP(c, 0.015 * peri, True)
                pts = [Point2D(p[0][0] * effective_scale, (img_h - p[0][1]) * effective_scale) for p in approx]
                area_m2 = cv2.contourArea(c) * (effective_scale ** 2)
                rooms.append(
                    RoomPolygon(
                        id=f"room_{idx + 1}",
                        name=f"Room {idx + 1}",
                        points=pts,
                    )
                )

        floor_plan = FloorPlan(
            walls=final_walls,
            rooms=rooms,
            scale=effective_scale,
            validation=report,
            metadata={
                "source": str(path),
                "image_width_px": img_w,
                "image_height_px": img_h,
                "bound_openings": bound_count,
                "doors_detected": len(doors_data),
                "windows_detected": len(windows_data),
            },
        )

        return floor_plan
