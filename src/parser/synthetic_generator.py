"""Synthetic architectural benchmark generator producing ground-truth blueprints and JSON specs."""

from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any, Dict, List, Tuple

import cv2
import numpy as np

from src.config import CONFIG
from src.models import (
    FloorPlan,
    OpeningInterval,
    OpeningType,
    Point2D,
    RoomPolygon,
    WallEdge,
)


class SyntheticBenchmarkGenerator:
    """
    Generates realistic, dimensioned architectural floor plans.
    Outputs both high-resolution CAD-style raster images and structured JSON ground truth.
    """

    def __init__(self, pixels_per_meter: float = 50.0) -> None:
        self.ppm = pixels_per_meter
        self.scale_m_per_px = 1.0 / pixels_per_meter

    def generate_apartment_plan(self) -> Tuple[FloorPlan, Dict[str, Any]]:
        """
        Generates a 2-bedroom modern apartment layout in metric coordinates (meters).
        Total footprint: 10.0m x 8.0m (80.0 m²).
        Rooms:
        - Living & Dining (22.5 m²)
        - Kitchen (17.5 m²)
        - Foyer & Hall (9.0 m²)
        - Bathroom (6.6 m²)
        - Bedroom 2 / Guest (12.5 m²)
        - Master Bedroom (13.75 m²)
        """
        walls: List[WallEdge] = [
            # Exterior Walls (thickness 0.25m)
            # South: (0,0) -> (10,0)
            WallEdge(id="W_EXT_S", start=Point2D(0.0, 0.0), end=Point2D(10.0, 0.0), thickness=0.25),
            # East: (10,0) -> (10,8)
            WallEdge(id="W_EXT_E", start=Point2D(10.0, 0.0), end=Point2D(10.0, 8.0), thickness=0.25),
            # North: (10,8) -> (0,8)
            WallEdge(id="W_EXT_N", start=Point2D(10.0, 8.0), end=Point2D(0.0, 8.0), thickness=0.25),
            # West: (0,8) -> (0,0)
            WallEdge(id="W_EXT_W", start=Point2D(0.0, 8.0), end=Point2D(0.0, 0.0), thickness=0.25),

            # Central vertical spine wall at x = 4.5m: divides west living/kitchen from east bedrooms
            WallEdge(id="W_SPINE", start=Point2D(4.5, 0.0), end=Point2D(4.5, 8.0), thickness=0.20),

            # West horizontal partition: separates Kitchen [0..4.5, 0..3.5] from Living [0..4.5, 3.5..8]
            WallEdge(id="W_INT_KIT", start=Point2D(0.0, 3.5), end=Point2D(4.5, 3.5), thickness=0.15),

            # East horizontal partitions:
            # Separates Bathroom/Foyer from Bedroom 2 at y = 3.0m: (4.5, 3.0) -> (10.0, 3.0)
            WallEdge(id="W_INT_BED2", start=Point2D(4.5, 3.0), end=Point2D(10.0, 3.0), thickness=0.15),
            # Separates Bedroom 2 from Master Bedroom at y = 5.5m: (4.5, 5.5) -> (10.0, 5.5)
            WallEdge(id="W_INT_MBED", start=Point2D(4.5, 5.5), end=Point2D(10.0, 5.5), thickness=0.15),

            # Bathroom vertical partition at x = 7.0m: separates Bath [4.5..7.0, 0..3] from Foyer [7.0..10, 0..3]
            WallEdge(id="W_INT_BATH", start=Point2D(7.0, 0.0), end=Point2D(7.0, 3.0), thickness=0.15),
        ]

        # -------------------------------------------------------------
        # OPENINGS: DOORS & WINDOWS (Strict 1D Parametric Intervals)
        # Each door has an unambiguous hinge location and swing direction
        # -------------------------------------------------------------

        # 1. Main Entry Door on south exterior wall: dist 7.8m to 8.8m (1.0m width)
        # Hinge at 7.8m (adjacent to interior dividing wall), swings inward into Foyer (+y)
        walls[0].add_opening(OpeningInterval(
            start_dist=7.8,
            end_dist=8.8,
            opening_type=OpeningType.DOOR,
            id="DOOR_ENTRY",
            height=2.1,
            sill_height=0.0,
            metadata={"hinge": "start", "swing_side": 1},
        ))

        # 2. Kitchen Window on south exterior wall: dist 1.5m to 3.0m (1.5m width)
        walls[0].add_opening(OpeningInterval(
            start_dist=1.5,
            end_dist=3.0,
            opening_type=OpeningType.WINDOW,
            id="WIN_KITCHEN",
            height=1.2,
            sill_height=0.9,
        ))

        # 3. Bathroom Privacy Window on south exterior wall: dist 5.2m to 6.0m (0.8m width)
        walls[0].add_opening(OpeningInterval(
            start_dist=5.2,
            end_dist=6.0,
            opening_type=OpeningType.WINDOW,
            id="WIN_BATH",
            height=0.8,
            sill_height=1.4,
        ))

        # 4. Bedroom 2 Window on east exterior wall: dist 3.6m to 5.0m (1.4m width)
        walls[1].add_opening(OpeningInterval(
            start_dist=3.6,
            end_dist=5.0,
            opening_type=OpeningType.WINDOW,
            id="WIN_BED2",
            height=1.3,
            sill_height=0.85,
        ))

        # 5. Master Bedroom Window on east exterior wall: dist 6.0m to 7.5m (1.5m width)
        walls[1].add_opening(OpeningInterval(
            start_dist=6.0,
            end_dist=7.5,
            opening_type=OpeningType.WINDOW,
            id="WIN_MBED",
            height=1.4,
            sill_height=0.75,
        ))

        # 6. Large Living Room Panoramic Window on north exterior wall:
        # Note: north wall runs (10,8) -> (0,8), so dist 6.0 to 8.5 corresponds to x in [1.5, 4.0]
        walls[2].add_opening(OpeningInterval(
            start_dist=6.0,
            end_dist=8.5,
            opening_type=OpeningType.WINDOW,
            id="WIN_LIVING",
            height=1.5,
            sill_height=0.65,
        ))

        # 7. Corridor Door / Passage on central spine (W_SPINE): dist 3.8m to 4.7m (0.9m width)
        # Hinge at 3.8m, swings into living room hallway (-x, swing_side = 1)
        walls[4].add_opening(OpeningInterval(
            start_dist=3.8,
            end_dist=4.7,
            opening_type=OpeningType.DOOR,
            id="DOOR_CORRIDOR",
            height=2.1,
            sill_height=0.0,
            metadata={"hinge": "start", "swing_side": 1},
        ))

        # 8. Kitchen Door on W_INT_KIT: dist 1.2m to 2.1m (0.9m width)
        # Centered along kitchen wall, hinge at 1.2m, swings inward into Kitchen (-y, swing_side = -1)
        walls[5].add_opening(OpeningInterval(
            start_dist=1.2,
            end_dist=2.1,
            opening_type=OpeningType.DOOR,
            id="DOOR_KITCHEN",
            height=2.1,
            sill_height=0.0,
            metadata={"hinge": "start", "swing_side": -1},
        ))

        # 9. Bathroom Door on W_INT_BED2: dist 0.4m to 1.3m (0.9m width)
        # Hinge at 0.4m (near central spine at x=4.5), swings inward into bathroom (-y, swing_side = -1)
        walls[6].add_opening(OpeningInterval(
            start_dist=0.4,
            end_dist=1.3,
            opening_type=OpeningType.DOOR,
            id="DOOR_BATH",
            height=2.1,
            sill_height=0.0,
            metadata={"hinge": "start", "swing_side": -1},
        ))

        # 10. Bedroom 2 Door on W_INT_BED2: dist 3.2m to 4.1m (0.9m width)
        # Hinge at 3.2m (adjacent to east partition), swings inward into Bedroom 2 (+y, swing_side = 1)
        walls[6].add_opening(OpeningInterval(
            start_dist=3.2,
            end_dist=4.1,
            opening_type=OpeningType.DOOR,
            id="DOOR_BED2",
            height=2.1,
            sill_height=0.0,
            metadata={"hinge": "start", "swing_side": 1},
        ))

        # 11. Master Bedroom Door on W_INT_MBED: dist 0.4m to 1.3m (0.9m width)
        # Hinge at 0.4m (near central spine at x=4.5), swings inward into Master Bedroom (+y, swing_side = 1)
        walls[7].add_opening(OpeningInterval(
            start_dist=0.4,
            end_dist=1.3,
            opening_type=OpeningType.DOOR,
            id="DOOR_MBED",
            height=2.1,
            sill_height=0.0,
            metadata={"hinge": "start", "swing_side": 1},
        ))

        # Enclosed Rooms with distinct architectural colors
        rooms: List[RoomPolygon] = [
            RoomPolygon(
                id="room_kitchen",
                name="Kitchen & Dining",
                points=[Point2D(0.0, 0.0), Point2D(4.5, 0.0), Point2D(4.5, 3.5), Point2D(0.0, 3.5)],
                color=(238, 224, 212, 255),
            ),
            RoomPolygon(
                id="room_living",
                name="Living Room",
                points=[Point2D(0.0, 3.5), Point2D(4.5, 3.5), Point2D(4.5, 8.0), Point2D(0.0, 8.0)],
                color=(242, 238, 230, 255),
            ),
            RoomPolygon(
                id="room_bath",
                name="Bathroom",
                points=[Point2D(4.5, 0.0), Point2D(7.0, 0.0), Point2D(7.0, 3.0), Point2D(4.5, 3.0)],
                color=(218, 236, 240, 255),
            ),
            RoomPolygon(
                id="room_foyer",
                name="Foyer & Hall",
                points=[Point2D(7.0, 0.0), Point2D(10.0, 0.0), Point2D(10.0, 3.0), Point2D(7.0, 3.0)],
                color=(232, 230, 222, 255),
            ),
            RoomPolygon(
                id="room_bed2",
                name="Bedroom 2",
                points=[Point2D(4.5, 3.0), Point2D(10.0, 3.0), Point2D(10.0, 5.5), Point2D(4.5, 5.5)],
                color=(224, 236, 228, 255),
            ),
            RoomPolygon(
                id="room_mbed",
                name="Master Bedroom",
                points=[Point2D(4.5, 5.5), Point2D(10.0, 5.5), Point2D(10.0, 8.0), Point2D(4.5, 8.0)],
                color=(232, 226, 236, 255),
            ),
        ]

        floor_plan = FloorPlan(
            walls=walls,
            rooms=rooms,
            scale=1.0,  # SI meters
            metadata={"name": "2-Bedroom Benchmark Apartment", "generator": "SyntheticBenchmarkGenerator"},
        )

        return floor_plan, floor_plan.to_dict()

    def render_blueprint_image(
        self, floor_plan: FloorPlan, margin_meters: float = 1.5
    ) -> Tuple[np.ndarray, Dict[str, Any]]:
        """
        Renders floor plan into a professional architectural CAD blueprint raster image.
        Uses rigorous vector geometry for door swing arcs (true 90-degree circular sweeps
        anchored at wall jamb hinges) and architectural double-glazing window symbols.
        """
        all_x: List[float] = []
        all_y: List[float] = []
        for w in floor_plan.walls:
            all_x.extend([w.start.x, w.end.x])
            all_y.extend([w.start.y, w.end.y])

        min_x, max_x = min(all_x), max(all_x)
        min_y, max_y = min(all_y), max(all_y)

        ox_m = min_x - margin_meters
        oy_m = min_y - margin_meters
        width_m = (max_x - min_x) + 2 * margin_meters
        height_m = (max_y - min_y) + 2 * margin_meters + 1.0

        img_w = int(math.ceil(width_m * self.ppm))
        img_h = int(math.ceil(height_m * self.ppm))

        # Crisp CAD blueprint canvas (pure white)
        img = np.full((img_h, img_w, 3), 255, dtype=np.uint8)

        def to_px(m_pt: Point2D) -> Tuple[int, int]:
            px = int(round((m_pt.x - ox_m) * self.ppm))
            py = int(round(img_h - (m_pt.y - oy_m) * self.ppm))
            return (px, py)

        def to_px_xy(x: float, y: float) -> Tuple[int, int]:
            return to_px(Point2D(x, y))

        # 1. Draw solid wall segments leaving clean apertures
        for wall in floor_plan.walls:
            thick_px = max(2, int(round(wall.thickness * self.ppm)))
            solid_intervals = wall.get_solid_intervals()

            for s_dist, e_dist in solid_intervals:
                p_s = wall.point_at_distance(s_dist)
                p_e = wall.point_at_distance(e_dist)
                cv2.line(img, to_px(p_s), to_px(p_e), (35, 35, 35), thick_px)

        # 2. Draw Doors and Windows with true vector architectural symbols
        for wall in floor_plan.walls:
            ux, uy = wall.direction
            nx, ny = wall.normal

            for op in wall.openings:
                s0 = op.start_dist
                s1 = op.end_dist
                w_m = s1 - s0

                # World points of the aperture opening jambs
                p_s0 = wall.point_at_distance(s0)
                p_s1 = wall.point_at_distance(s1)

                if op.opening_type == OpeningType.DOOR:
                    # Determine hinge side and swing direction
                    hinge_pref = op.metadata.get("hinge", "start")
                    swing_side = float(op.metadata.get("swing_side", 1))

                    if hinge_pref == "end":
                        p_hinge = p_s1
                        p_latch = p_s0
                        u_closed_x, u_closed_y = -ux, -uy
                    else:
                        p_hinge = p_s0
                        p_latch = p_s1
                        u_closed_x, u_closed_y = ux, uy

                    # Perpendicular open direction into room
                    u_open_x = swing_side * nx
                    u_open_y = swing_side * ny

                    # Tip of door leaf in open 90-degree position
                    p_open = Point2D(
                        p_hinge.x + w_m * u_open_x,
                        p_hinge.y + w_m * u_open_y,
                    )

                    # Draw Door Leaf Line (rich wood color, thickness 2px)
                    cv2.line(img, to_px(p_hinge), to_px(p_open), (50, 85, 155), 2, cv2.LINE_AA)

                    # Draw true 90-degree circular swing arc from closed latch to open tip
                    arc_pts: List[Tuple[int, int]] = []
                    num_arc_segments = 24
                    for step in range(num_arc_segments + 1):
                        theta = (math.pi / 2.0) * (step / float(num_arc_segments))
                        arc_x = p_hinge.x + w_m * (math.cos(theta) * u_closed_x + math.sin(theta) * u_open_x)
                        arc_y = p_hinge.y + w_m * (math.cos(theta) * u_closed_y + math.sin(theta) * u_open_y)
                        arc_pts.append(to_px_xy(arc_x, arc_y))

                    arc_arr = np.array(arc_pts, dtype=np.int32).reshape((-1, 1, 2))
                    cv2.polylines(img, [arc_arr], isClosed=False, color=(165, 165, 165), thickness=1, lineType=cv2.LINE_AA)

                    # Draw small hinge dot indicator
                    cv2.circle(img, to_px(p_hinge), 3, (40, 40, 40), -1)

                elif op.opening_type == OpeningType.WINDOW:
                    # Draw Architectural Window Symbol:
                    # Cutout jamb caps
                    half_wt = wall.thickness * 0.5
                    for jamb_pt in (p_s0, p_s1):
                        j_a = Point2D(jamb_pt.x - nx * half_wt, jamb_pt.y - ny * half_wt)
                        j_b = Point2D(jamb_pt.x + nx * half_wt, jamb_pt.y + ny * half_wt)
                        cv2.line(img, to_px(j_a), to_px(j_b), (80, 80, 80), 1, cv2.LINE_AA)

                    # Protruding exterior stone sill
                    sill_offset = half_wt + 0.04
                    sill_s = Point2D(p_s0.x - ux * 0.04 + nx * sill_offset, p_s0.y - uy * 0.04 + ny * sill_offset)
                    sill_e = Point2D(p_s1.x + ux * 0.04 + nx * sill_offset, p_s1.y + uy * 0.04 + ny * sill_offset)
                    cv2.line(img, to_px(sill_s), to_px(sill_e), (120, 115, 110), 2, cv2.LINE_AA)

                    # Two distinct parallel glass lines in bright architectural cyan
                    glass_off = half_wt * 0.35
                    g1_s = Point2D(p_s0.x - nx * glass_off, p_s0.y - ny * glass_off)
                    g1_e = Point2D(p_s1.x - nx * glass_off, p_s1.y - ny * glass_off)
                    g2_s = Point2D(p_s0.x + nx * glass_off, p_s0.y + ny * glass_off)
                    g2_e = Point2D(p_s1.x + nx * glass_off, p_s1.y + ny * glass_off)

                    cv2.line(img, to_px(g1_s), to_px(g1_e), (210, 150, 0), 2, cv2.LINE_AA)  # BGR Cyan
                    cv2.line(img, to_px(g2_s), to_px(g2_e), (210, 150, 0), 2, cv2.LINE_AA)

                    # Center mullion divider tick
                    m_center = wall.point_at_distance(0.5 * (s0 + s1))
                    m_a = Point2D(m_center.x - nx * half_wt, m_center.y - ny * half_wt)
                    m_b = Point2D(m_center.x + nx * half_wt, m_center.y + ny * half_wt)
                    cv2.line(img, to_px(m_a), to_px(m_b), (60, 60, 60), 2, cv2.LINE_AA)

        # 3. Draw Room Text Labels
        for room in floor_plan.rooms:
            c = room.centroid
            cx_px, cy_px = to_px(c)
            # Label
            cv2.putText(
                img,
                room.name.upper(),
                (cx_px - 48, cy_px - 5),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.42,
                (60, 60, 60),
                1,
                cv2.LINE_AA,
            )
            area_str = f"{room.area:.1f} m2"
            cv2.putText(
                img,
                area_str,
                (cx_px - 22, cy_px + 14),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.38,
                (100, 100, 100),
                1,
                cv2.LINE_AA,
            )

        # 4. Draw Metric Scale Bar: 5-meter benchmark scale bar
        scale_start_x = 40
        scale_y = img_h - 35
        bar_len_m = 5.0
        bar_len_px = int(round(bar_len_m * self.ppm))

        # Main scale bar line
        cv2.line(img, (scale_start_x, scale_y), (scale_start_x + bar_len_px, scale_y), (20, 20, 20), 3)

        # Tick marks at each meter
        for m in range(int(bar_len_m) + 1):
            tick_x = int(round(scale_start_x + m * self.ppm))
            tick_h = 8 if m in (0, int(bar_len_m)) else 5
            cv2.line(img, (tick_x, scale_y - tick_h), (tick_x, scale_y + tick_h), (20, 20, 20), 2)
            cv2.putText(
                img,
                f"{m}m",
                (tick_x - 8, scale_y - 12),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.35,
                (30, 30, 30),
                1,
                cv2.LINE_AA,
            )

        cv2.putText(
            img,
            f"SCALE 1:{int(round(self.ppm))} (1 px = {self.scale_m_per_px:.4f} m)",
            (scale_start_x, scale_y + 22),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.40,
            (40, 40, 40),
            1,
            cv2.LINE_AA,
        )

        metadata = {
            "image_width_px": img_w,
            "image_height_px": img_h,
            "pixels_per_meter": self.ppm,
            "scale_m_per_px": self.scale_m_per_px,
            "origin_m": (ox_m, oy_m),
            "scale_bar": {
                "start_px": (scale_start_x, scale_y),
                "length_px": bar_len_px,
                "length_m": bar_len_m,
            },
        }

        return img, metadata

    def export_benchmark_dataset(self, out_dir: str | Path) -> Tuple[Path, Path]:
        """Saves benchmark floor plan image (PNG) and ground truth JSON."""
        out_path = Path(out_dir)
        out_path.mkdir(parents=True, exist_ok=True)

        plan, plan_dict = self.generate_apartment_plan()
        img, img_meta = self.render_blueprint_image(plan)

        img_file = out_path / "benchmark_floorplan.png"
        json_file = out_path / "benchmark_ground_truth.json"

        cv2.imwrite(str(img_file), img)

        ground_truth = {
            "floor_plan": plan_dict,
            "image_metadata": img_meta,
        }

        with open(json_file, "w", encoding="utf-8") as f:
            json.dump(ground_truth, f, indent=2)

        return img_file, json_file
