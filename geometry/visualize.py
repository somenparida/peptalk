"""
Phase 7: Visual Geometry Preview Generator for Member 2.

Generates geometry_preview.png illustrating original walls, cleaned walls,
doors, windows, and room boundaries against the blueprint image canvas.
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
    output_path: str = "geometry_output/geometry_preview.png"
) -> Path:
    """
    Renders an informative 2D CAD/blueprint preview image comparing raw vs cleaned geometry.
    """
    out_file = Path(output_path).resolve()
    out_file.parent.mkdir(parents=True, exist_ok=True)

    img_meta = cleaned_scene.get("image", {"width": 512, "height": 260})
    w_px = img_meta.get("width", 512)
    h_px = img_meta.get("height", 260)

    fig, ax = plt.subplots(figsize=(12, 6.5), dpi=150)
    ax.set_facecolor("#181b20")
    fig.patch.set_facecolor("#121417")

    # 1. Image boundary frame
    border = Rectangle((0, 0), w_px, h_px, fill=False, edgecolor="#374151", linewidth=1.5, linestyle=":")
    ax.add_patch(border)

    # 2. Room polygons (pastel semi-transparent fills)
    room_colors = ["#3b82f633", "#10b98133", "#8b5cf633", "#f59e0b33", "#ec489933"]
    for idx, r in enumerate(cleaned_scene.get("rooms", [])):
        pts = r["geometry"]["polygon"]
        color = room_colors[idx % len(room_colors)]
        mpl_poly = MplPolygon(pts, closed=True, facecolor=color, edgecolor="#60a5fa", linewidth=1.2, linestyle="--")
        ax.add_patch(mpl_poly)

        # Label centroid
        c = r["geometry"].get("centroid")
        if c:
            label = r.get("label", r["id"])
            ax.text(c[0], c[1], f"{label}\n({r['geometry']['area']:.0f} px²)",
                    color="#93c5fd", fontsize=8, ha="center", va="center", weight="bold")

    # 3. Raw walls (dashed faint lines to see original locations)
    for w in raw_scene.get("walls", []):
        s = w.get("start", [0, 0])
        e = w.get("end", [0, 0])
        ax.plot([s[0], e[0]], [s[1], e[1]], color="#6b7280", linestyle=":", linewidth=1.0, alpha=0.6)

    # 4. Cleaned walls (solid high-contrast lines with thickness representation)
    for w in cleaned_scene.get("walls", []):
        s = w["geometry"]["start"]
        e = w["geometry"]["end"]
        th = max(2.0, w["geometry"]["thickness"] * 0.4)
        ax.plot([s[0], e[0]], [s[1], e[1]], color="#e5e7eb", linewidth=th, solid_capstyle="round", alpha=0.9)

        # Wall ID label at midpoint
        mx = (s[0] + e[0]) / 2.0
        my = (s[1] + e[1]) / 2.0
        ax.text(mx, my, w["id"], color="#fbbf24", fontsize=7, ha="center", va="bottom", weight="bold")

    # 5. Doors (distinct green markers)
    for d in cleaned_scene.get("doors", []):
        geom = d.get("geometry", {})
        c = geom.get("center")
        if c:
            ax.plot(c[0], c[1], marker="s", markersize=7, color="#22c55e", markeredgecolor="#ffffff")
            s = geom.get("start")
            e = geom.get("end")
            if s and e:
                ax.plot([s[0], e[0]], [s[1], e[1]], color="#4ade80", linewidth=3.5)
            ax.text(c[0], c[1] - 4, d["id"], color="#4ade80", fontsize=7, ha="center", va="bottom", weight="bold")

    # 6. Windows (distinct cyan markers)
    for win in cleaned_scene.get("windows", []):
        geom = win.get("geometry", {})
        c = geom.get("center")
        if c:
            ax.plot(c[0], c[1], marker="o", markersize=6, color="#06b6d4", markeredgecolor="#ffffff")
            s = geom.get("start")
            e = geom.get("end")
            if s and e:
                ax.plot([s[0], e[0]], [s[1], e[1]], color="#38bdf8", linewidth=3.0)
            ax.text(c[0], c[1] + 4, win["id"], color="#38bdf8", fontsize=7, ha="center", va="top", weight="bold")

    # Canvas orientation (image coordinates: y down)
    ax.set_xlim(-15, w_px + 15)
    ax.set_ylim(h_px + 15, -15)
    ax.set_aspect("equal")

    # Legend & Header
    legend_elements = [
        plt.Line2D([0], [0], color="#e5e7eb", lw=3, label="Cleaned Wall"),
        plt.Line2D([0], [0], color="#6b7280", lw=1.5, ls=":", label="Raw Source Wall"),
        plt.Line2D([0], [0], marker="s", color="#22c55e", lw=0, label="Door"),
        plt.Line2D([0], [0], marker="o", color="#06b6d4", lw=0, label="Window"),
        plt.Line2D([0], [0], color="#60a5fa", lw=1.5, ls="--", label="Room Boundary"),
    ]
    ax.legend(handles=legend_elements, loc="upper right", facecolor="#1f242d", edgecolor="#374151",
              labelcolor="#e5e7eb", fontsize=8)

    ax.set_title(
        f"Member 2 Geometry Preview | Canvas {w_px}x{h_px} px | "
        f"{len(cleaned_scene.get('walls', []))} Walls, {len(cleaned_scene.get('doors', []))} Doors, "
        f"{len(cleaned_scene.get('windows', []))} Windows, {len(cleaned_scene.get('rooms', []))} Rooms",
        color="#f3f4f6", fontsize=11, weight="bold", pad=12
    )

    ax.tick_params(colors="#9ca3af", labelsize=8)
    for spine in ax.spines.values():
        spine.set_color("#374151")

    plt.tight_layout()
    fig.savefig(out_file, bbox_inches="tight", dpi=150)
    plt.close(fig)

    return out_file
