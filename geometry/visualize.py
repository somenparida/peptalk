"""
Phase 7: Visual Geometry Preview Generator for Member 2.

Generates geometry_preview.png illustrating original walls, cleaned walls,
wall start/end points, doors, windows, room boundaries, and warning markers
against the blueprint image canvas.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Dict, Any, Optional
import matplotlib
matplotlib.use("Agg")  # Non-interactive backend
import matplotlib.pyplot as plt
from matplotlib.patches import Polygon as MplPolygon, Rectangle
import numpy as np


def generate_preview(
    raw_scene: Dict[str, Any],
    cleaned_scene: Dict[str, Any],
    output_path: str = "geometry_output/geometry_preview.png",
    validation_report: Optional[Dict[str, Any]] = None
) -> Path:
    """
    Renders an informative 2D CAD/blueprint preview image comparing raw vs cleaned geometry,
    including wall IDs, start/end points, door/window IDs, room IDs, and warning markers.
    """
    out_file = Path(output_path).resolve()
    out_file.parent.mkdir(parents=True, exist_ok=True)

    img_meta = cleaned_scene.get("image", {"width": 512, "height": 260})
    w_px = img_meta.get("width", 512)
    h_px = img_meta.get("height", 260)

    fig, ax = plt.subplots(figsize=(13, 7.0), dpi=150)
    ax.set_facecolor("#181b20")
    fig.patch.set_facecolor("#121417")

    # 1. Image boundary frame
    border = Rectangle((0, 0), w_px, h_px, fill=False, edgecolor="#374151", linewidth=1.5, linestyle=":")
    ax.add_patch(border)

    # 2. Room polygons (pastel semi-transparent fills with IDs)
    room_colors = ["#3b82f633", "#10b98133", "#8b5cf633", "#f59e0b33", "#ec489933"]
    for idx, r in enumerate(cleaned_scene.get("rooms", [])):
        pts = r.get("geometry", {}).get("polygon", r.get("polygon", []))
        if not pts:
            continue
        color = room_colors[idx % len(room_colors)]
        mpl_poly = MplPolygon(pts, closed=True, facecolor=color, edgecolor="#60a5fa", linewidth=1.2, linestyle="--")
        ax.add_patch(mpl_poly)

        # Label centroid with room ID and area
        c = r.get("geometry", {}).get("centroid")
        if not c:
            xs = [p[0] for p in pts]
            ys = [p[1] for p in pts]
            c = [sum(xs) / len(xs), sum(ys) / len(ys)]
        area = r.get("geometry", {}).get("area", 0)
        label = r.get("label", r["id"])
        ax.text(c[0], c[1], f"[{r['id']}] {label}\n({area:.0f} px²)",
                color="#93c5fd", fontsize=8, ha="center", va="center", weight="bold",
                bbox=dict(boxstyle="round,pad=0.2", facecolor="#1e293b", edgecolor="#3b82f6", alpha=0.7, lw=0.8))

    # 3. Raw walls (dashed faint lines to show Member 1 raw inputs)
    for w in raw_scene.get("walls", []):
        s = w.get("start", [0, 0])
        e = w.get("end", [0, 0])
        ax.plot([s[0], e[0]], [s[1], e[1]], color="#6b7280", linestyle=":", linewidth=1.0, alpha=0.5)

    # 4. Cleaned walls (solid high-contrast lines with endpoints and thickness)
    for w in cleaned_scene.get("walls", []):
        s = w["geometry"]["start"]
        e = w["geometry"]["end"]
        th = max(2.5, w["geometry"]["thickness"] * 0.35)
        ax.plot([s[0], e[0]], [s[1], e[1]], color="#f3f4f6", linewidth=th, solid_capstyle="round", alpha=0.95, zorder=3)

        # Wall start point (blue dot) and end point (red dot)
        ax.plot(s[0], s[1], marker="o", markersize=4, color="#60a5fa", markeredgecolor="#1e293b", zorder=4)
        ax.plot(e[0], e[1], marker="o", markersize=4, color="#f87171", markeredgecolor="#1e293b", zorder=4)

        # Wall ID label at midpoint
        mx = (s[0] + e[0]) / 2.0
        my = (s[1] + e[1]) / 2.0
        ax.text(mx, my - 3, w["id"], color="#fbbf24", fontsize=7.5, ha="center", va="bottom", weight="bold",
                bbox=dict(boxstyle="square,pad=0.15", facecolor="#1f2937", edgecolor="#d97706", alpha=0.8, lw=0.6), zorder=5)

    # 5. Doors (distinct green markers and lines with door IDs)
    for d in cleaned_scene.get("doors", []):
        geom = d.get("geometry", {})
        c = geom.get("center")
        if c:
            ax.plot(c[0], c[1], marker="s", markersize=7, color="#22c55e", markeredgecolor="#ffffff", zorder=6)
            s = geom.get("start")
            e = geom.get("end")
            if s and e:
                ax.plot([s[0], e[0]], [s[1], e[1]], color="#4ade80", linewidth=4.0, zorder=5)
            ax.text(c[0], c[1] - 5, f"{d['id']} (w={d['width']:.0f})",
                    color="#4ade80", fontsize=7.5, ha="center", va="bottom", weight="bold",
                    bbox=dict(boxstyle="round,pad=0.15", facecolor="#064e3b", edgecolor="#10b981", alpha=0.85, lw=0.6), zorder=7)

    # 6. Windows (distinct cyan markers and lines with window IDs)
    for win in cleaned_scene.get("windows", []):
        geom = win.get("geometry", {})
        c = geom.get("center")
        if c:
            ax.plot(c[0], c[1], marker="D", markersize=6, color="#06b6d4", markeredgecolor="#ffffff", zorder=6)
            s = geom.get("start")
            e = geom.get("end")
            if s and e:
                ax.plot([s[0], e[0]], [s[1], e[1]], color="#38bdf8", linewidth=3.5, zorder=5)
            ax.text(c[0], c[1] + 6, f"{win['id']} (w={win['width']:.0f})",
                    color="#38bdf8", fontsize=7.5, ha="center", va="top", weight="bold",
                    bbox=dict(boxstyle="round,pad=0.15", facecolor="#083344", edgecolor="#06b6d4", alpha=0.85, lw=0.6), zorder=7)

    # 7. Warning markers (highlighting warnings like boundary door position)
    warnings = []
    if validation_report:
        warnings = validation_report.get("warnings", [])
    elif "validation" in cleaned_scene:
        warnings = cleaned_scene["validation"].get("warnings", [])

    for w_iss in warnings:
        el_id = w_iss.get("element_id")
        # Find element center
        elem = next((d for d in cleaned_scene.get("doors", []) if d["id"] == el_id), None)
        if not elem:
            elem = next((w for w in cleaned_scene.get("windows", []) if w["id"] == el_id), None)
        if elem and "geometry" in elem and "center" in elem["geometry"]:
            cx, cy = elem["geometry"]["center"]
            # Warning ring
            ax.plot(cx, cy, marker="o", markersize=14, color="none", markeredgecolor="#f59e0b", markeredgewidth=2.0, zorder=8)
            ax.text(cx + 8, cy, "!", color="#f59e0b", fontsize=9, weight="bold",
                    bbox=dict(boxstyle="circle,pad=0.2", facecolor="#78350f", edgecolor="#f59e0b", alpha=0.9, lw=1.0), zorder=9)

    # Canvas orientation (image coordinates: Y increases downwards)
    ax.set_xlim(-15, w_px + 15)
    ax.set_ylim(h_px + 15, -15)
    ax.set_aspect("equal")

    # Legend
    legend_elements = [
        plt.Line2D([0], [0], color="#f3f4f6", lw=3.5, label="Cleaned Wall"),
        plt.Line2D([0], [0], color="#60a5fa", marker="o", lw=0, markersize=5, label="Wall Start (S)"),
        plt.Line2D([0], [0], color="#f87171", marker="o", lw=0, markersize=5, label="Wall End (E)"),
        plt.Line2D([0], [0], marker="s", color="#22c55e", lw=0, markersize=7, label="Door (Center)"),
        plt.Line2D([0], [0], marker="D", color="#06b6d4", lw=0, markersize=6, label="Window (Center)"),
        plt.Line2D([0], [0], color="#60a5fa", lw=1.5, ls="--", label="Room Boundary"),
        plt.Line2D([0], [0], marker="o", color="#f59e0b", markeredgecolor="#f59e0b", lw=0, markersize=8, fillstyle="none", markeredgewidth=2, label="Warning Marker (!)"),
        plt.Line2D([0], [0], color="#6b7280", lw=1.2, ls=":", label="Raw Source Wall"),
    ]
    ax.legend(handles=legend_elements, loc="upper right", facecolor="#1f242d", edgecolor="#374151",
              labelcolor="#e5e7eb", fontsize=7.5, framealpha=0.9)

    warn_count = len(warnings)
    status_text = "PASS" if not any(w_iss.get("severity") == "ERROR" for w_iss in warnings) else "FAIL"
    ax.set_title(
        f"Member 2 2D CAD Debug Preview | Canvas: {w_px}x{h_px} px | "
        f"{len(cleaned_scene.get('walls', []))} Walls, {len(cleaned_scene.get('doors', []))} Doors, "
        f"{len(cleaned_scene.get('windows', []))} Windows, {len(cleaned_scene.get('rooms', []))} Rooms | "
        f"Validation: {status_text} ({warn_count} Warnings)",
        color="#f3f4f6", fontsize=10.5, weight="bold", pad=12
    )

    ax.tick_params(colors="#9ca3af", labelsize=8)
    for spine in ax.spines.values():
        spine.set_color("#374151")

    plt.tight_layout()
    fig.savefig(out_file, bbox_inches="tight", dpi=150)
    plt.close(fig)

    return out_file
