#!/usr/bin/env python3
import sys
import json
from pathlib import Path
import matplotlib.pyplot as plt
import numpy as np

BASE_DIR = Path(__file__).resolve().parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

RESULTS_JSON = BASE_DIR / "evaluation" / "results" / "results.json"
CHART_PATH = BASE_DIR / "evaluation" / "results" / "comparison_charts.png"


def generate_comparison_charts():
    """Generate Matplotlib comparison charts from evaluation results."""
    if not RESULTS_JSON.exists():
        print(f"Results JSON not found at {RESULTS_JSON}. Run evaluate.py first.")
        return

    with open(RESULTS_JSON, "r", encoding="utf-8") as f:
        res = json.load(f)

    b = res.get("baseline", {})
    p = res.get("proposed", {})

    metrics = ["Wall IoU", "Dim Rel Error (%)", "Invalid Geometry", "Composite Score"]
    baseline_vals = [
        b.get("wall_iou") or 0.0,
        b.get("dim_rel_pct") or 0.0,
        b.get("mean_invalid_geometry") or 0.0,
        b.get("composite_score") or 0.0,
    ]
    proposed_vals = [
        p.get("wall_iou") or 0.0,
        p.get("dim_rel_pct") or 0.0,
        p.get("mean_invalid_geometry") or 0.0,
        p.get("composite_score") or 0.0,
    ]

    fig, axes = plt.subplots(2, 2, figsize=(12, 9))
    fig.suptitle(f"HNX26EPS06 Baseline vs Proposed Pipeline ({res.get('split', 'heldout')} split)", fontsize=14, fontweight="bold")

    x = np.arange(2)
    width = 0.45

    colors_b = ["#e74c3c", "#e74c3c", "#e74c3c", "#e74c3c"]
    colors_p = ["#2ecc71", "#2ecc71", "#2ecc71", "#2ecc71"]

    # Chart 1: Wall IoU
    ax1 = axes[0, 0]
    bars = ax1.bar(["Baseline", "Proposed"], [baseline_vals[0], proposed_vals[0]], color=["#e74c3c", "#2ecc71"], width=width)
    ax1.set_title("Wall Layout IoU (Higher is Better)", fontsize=11)
    ax1.set_ylim(0, 1.1)
    for bar in bars:
        yval = bar.get_height()
        ax1.text(bar.get_x() + bar.get_width()/2.0, yval + 0.02, f"{yval:.3f}", ha="center", va="bottom", fontweight="bold")

    # Chart 2: Dimension Relative Error (%)
    ax2 = axes[0, 1]
    bars = ax2.bar(["Baseline", "Proposed"], [baseline_vals[1], proposed_vals[1]], color=["#e74c3c", "#2ecc71"], width=width)
    ax2.set_title("Mean Dimension Error % (Lower is Better)", fontsize=11)
    ax2.set_ylim(0, max(max(baseline_vals[1], proposed_vals[1]) * 1.3, 10.0))
    for bar in bars:
        yval = bar.get_height()
        ax2.text(bar.get_x() + bar.get_width()/2.0, yval + 0.5, f"{yval:.1f}%", ha="center", va="bottom", fontweight="bold")

    # Chart 3: Invalid Geometry Count
    ax3 = axes[1, 0]
    bars = ax3.bar(["Baseline", "Proposed"], [baseline_vals[2], proposed_vals[2]], color=["#e74c3c", "#2ecc71"], width=width)
    ax3.set_title("Mean Invalid Geometry Count (Lower is Better)", fontsize=11)
    ax3.set_ylim(0, max(max(baseline_vals[2], proposed_vals[2]) * 1.3, 5.0))
    for bar in bars:
        yval = bar.get_height()
        ax3.text(bar.get_x() + bar.get_width()/2.0, yval + 0.1, f"{yval:.2f}", ha="center", va="bottom", fontweight="bold")

    # Chart 4: Composite Score
    ax4 = axes[1, 1]
    bars = ax4.bar(["Baseline", "Proposed"], [baseline_vals[3], proposed_vals[3]], color=["#e74c3c", "#2ecc71"], width=width)
    ax4.set_title("Composite Benchmark Score / 100 (Higher is Better)", fontsize=11)
    ax4.set_ylim(0, 110)
    for bar in bars:
        yval = bar.get_height()
        ax4.text(bar.get_x() + bar.get_width()/2.0, yval + 2.0, f"{yval:.1f}", ha="center", va="bottom", fontweight="bold")

    plt.tight_layout(rect=[0, 0, 1, 0.95])
    CHART_PATH.parent.mkdir(parents=True, exist_ok=True)
    plt.savefig(str(CHART_PATH), dpi=150)
    plt.close()

    print(f"Saved comparison charts to {CHART_PATH}")


if __name__ == "__main__":
    generate_comparison_charts()
