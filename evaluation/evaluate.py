#!/usr/bin/env python3
import sys
import json
import argparse
import logging
from pathlib import Path
from typing import Dict, Any, List, Optional
import numpy as np

# Add project root to sys.path
BASE_DIR = Path(__file__).resolve().parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from integration.pipeline import reconstruct
from integration.config import DATA_DIR
from evaluation.metrics import (
    iou,
    rasterize_walls_to_mask,
    placement_error,
    abs_error,
    rel_error_pct,
    recall,
    compute_composite_score,
)
from scripts.check_dataset import load_ground_truth

log = logging.getLogger(__name__)


def evaluate_split(split_name: str = "heldout", out_dir: Path | str = "outputs") -> Dict[str, Any]:
    """Evaluate both baseline and proposed pipelines on a dataset split."""
    split_dir = DATA_DIR / split_name
    if not split_dir.exists():
        raise FileNotFoundError(f"Split directory not found: {split_dir}")

    plan_files = sorted(list(split_dir.glob("*.png")) + list(split_dir.glob("*.jpg")))

    results: Dict[str, Any] = {
        "split": split_name,
        "plans_evaluated": len(plan_files),
        "baseline": {},
        "proposed": {},
        "per_plan": {},
    }

    metrics_baseline = {"wall_iou": [], "dim_error_m": [], "dim_rel_pct": [], "recalls": [], "invalids": [], "scores": []}
    metrics_proposed = {"wall_iou": [], "dim_error_m": [], "dim_rel_pct": [], "recalls": [], "invalids": [], "scores": []}

    for pfile in plan_files:
        plan_name = pfile.stem
        gt = load_ground_truth(plan_name)

        # Run proposed
        res_prop = reconstruct(pfile, out_root=out_dir, mode="proposed")
        # Run baseline
        res_base = reconstruct(pfile, out_root=out_dir, mode="baseline")

        scene_p = res_prop["scene"]
        scene_b = res_base["scene"]

        # Compute metrics for proposed
        m_p = compute_plan_metrics(scene_p, gt, res_prop["report"])
        # Compute metrics for baseline
        m_b = compute_plan_metrics(scene_b, gt, res_base["report"])

        results["per_plan"][plan_name] = {
            "proposed": m_p,
            "baseline": m_b,
        }

        accumulate_metrics(metrics_proposed, m_p)
        accumulate_metrics(metrics_baseline, m_b)

    results["proposed"] = summarize_accumulated(metrics_proposed)
    results["baseline"] = summarize_accumulated(metrics_baseline)

    # Save results.json
    res_path = BASE_DIR / "evaluation" / "results" / "results.json"
    res_path.parent.mkdir(parents=True, exist_ok=True)
    with open(res_path, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2)

    return results


def compute_plan_metrics(scene: dict, gt: dict, report: dict) -> dict:
    cnts = gt.get("counts", {})
    gt_w_num = cnts.get("walls")
    gt_width = gt.get("building_width_m")

    # 1. Wall IoU (if gt mask exists)
    wall_iou_val = None
    gt_mask_path = gt.get("masks", {}).get("wall")
    if gt_mask_path and Path(gt_mask_path).exists():
        import cv2
        gt_mask = cv2.imread(str(gt_mask_path), cv2.IMREAD_GRAYSCALE)
        pred_mask = rasterize_walls_to_mask(scene.get("walls", []), gt_mask.shape)
        wall_iou_val = round(iou(pred_mask, gt_mask), 4)

    # 2. Dimension Error
    dim_err_m = None
    dim_rel_pct = None
    if gt_width is not None and scene.get("walls"):
        all_x = [w["start"][0] for w in scene["walls"]] + [w["end"][0] for w in scene["walls"]]
        pred_width = max(all_x) - min(all_x) if all_x else 0.0
        dim_err_m = round(abs_error(pred_width, gt_width), 3)
        dim_rel_pct = round(rel_error_pct(pred_width, gt_width), 2)

    # 3. Completeness Recall
    rec_val = None
    if gt_w_num is not None:
        rec_val = round(recall(len(scene.get("walls", [])), gt_w_num), 3)

    # 4. Geometry Validity
    counters = report.get("geometry_counters", {})

    # 5. Composite Score
    score = compute_composite_score(wall_iou_val, dim_rel_pct, rec_val, counters)

    return {
        "wall_iou": wall_iou_val,
        "dim_error_m": dim_err_m,
        "dim_rel_pct": dim_rel_pct,
        "completeness_recall": rec_val,
        "geometry_counters": counters,
        "composite_score": score,
    }


def accumulate_metrics(acc: dict, m: dict):
    if m["wall_iou"] is not None: acc["wall_iou"].append(m["wall_iou"])
    if m["dim_error_m"] is not None: acc["dim_error_m"].append(m["dim_error_m"])
    if m["dim_rel_pct"] is not None: acc["dim_rel_pct"].append(m["dim_rel_pct"])
    if m["completeness_recall"] is not None: acc["recalls"].append(m["completeness_recall"])
    if m["geometry_counters"]: acc["invalids"].append(sum(m["geometry_counters"].values()))
    acc["scores"].append(m["composite_score"])


def summarize_accumulated(acc: dict) -> dict:
    return {
        "wall_iou": round(float(np.mean(acc["wall_iou"])), 4) if acc["wall_iou"] else None,
        "dim_error_m": round(float(np.mean(acc["dim_error_m"])), 3) if acc["dim_error_m"] else None,
        "dim_rel_pct": round(float(np.mean(acc["dim_rel_pct"])), 2) if acc["dim_rel_pct"] else None,
        "completeness_recall": round(float(np.mean(acc["recalls"])), 3) if acc["recalls"] else None,
        "mean_invalid_geometry": round(float(np.mean(acc["invalids"])), 2) if acc["invalids"] else 0.0,
        "composite_score": round(float(np.mean(acc["scores"])), 2) if acc["scores"] else 0.0,
    }


def print_evaluation_summary(res: dict):
    b = res["baseline"]
    p = res["proposed"]

    def fmt(val, fmt_str=".2f", suffix=""):
        return f"{val:{fmt_str}}{suffix}" if val is not None else "n/a"

    print("========================================")
    print("HNX26EPS06 EVALUATION")
    print("========================================")
    print(f"Plans evaluated: {res['plans_evaluated']}   ({res['split']})\n")

    print(f"{'LAYOUT':40s} {'baseline':>10s} {'proposed':>10s}")
    print("-" * 62)
    print(f"{'Wall IoU:':40s} {fmt(b.get('wall_iou')):>10s} {fmt(p.get('wall_iou')):>10s}")

    print("\nDIMENSIONS")
    print("-" * 62)
    print(f"{'Mean absolute error (m):':40s} {fmt(b.get('dim_error_m')):>10s} {fmt(p.get('dim_error_m')):>10s}")
    print(f"{'Mean relative error (%):':40s} {fmt(b.get('dim_rel_pct'), '.2f', '%'):>10s} {fmt(p.get('dim_rel_pct'), '.2f', '%'):>10s}")

    print("\nCOMPLETENESS")
    print("-" * 62)
    print(f"{'Wall Recall:':40s} {fmt(b.get('completeness_recall')):>10s} {fmt(p.get('completeness_recall')):>10s}")

    print("\nGEOMETRY VALIDITY")
    print("-" * 62)
    print(f"{'Mean invalid / disconnected count:':40s} {fmt(b.get('mean_invalid_geometry')):>10s} {fmt(p.get('mean_invalid_geometry')):>10s}")

    print("\nBASELINE COMPARISON")
    print("-" * 62)
    print(f"{'Baseline composite score:':40s} {fmt(b.get('composite_score')):>10s}")
    print(f"{'Proposed composite score:':40s} {fmt(p.get('composite_score')):>10s}")
    print("========================================")


def main():
    parser = argparse.ArgumentParser(description="Evaluate pipeline against baseline")
    parser.add_argument("--split", type=str, default="heldout", choices=["heldout", "development", "demo"])
    args = parser.parse_args()

    results = evaluate_split(split_name=args.split)
    print_evaluation_summary(results)


if __name__ == "__main__":
    main()
