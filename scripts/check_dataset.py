#!/usr/bin/env python3
import json
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
EXPECTED_DIR = DATA_DIR / "expected"


def load_ground_truth(plan_name: str) -> dict:
    """Load ground truth JSON for plan, returning empty dict if missing."""
    gt_file = EXPECTED_DIR / f"{plan_name}.json"
    if not gt_file.exists():
        return {}
    try:
        with open(gt_file, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def main():
    splits = {
        "development": list((DATA_DIR / "development").glob("*.png")),
        "heldout": list((DATA_DIR / "heldout").glob("*.png")),
        "demo": list((DATA_DIR / "demo").glob("*.png")),
    }

    print("========================================")
    print("DATASET & GROUND TRUTH COVERAGE")
    print("========================================\n")

    for split_name, files in sorted(splits.items()):
        print(f"--- Split: {split_name} ({len(files)} plans) ---")
        for f in sorted(files, key=lambda p: p.name):
            plan_name = f.stem
            gt = load_ground_truth(plan_name)

            has_counts = "counts" in gt and gt["counts"] is not None
            has_dims = "building_width_m" in gt and gt["building_width_m"] is not None
            has_items = "items" in gt and gt["items"] is not None

            status_str = []
            if has_counts: status_str.append("counts")
            if has_dims: status_str.append("dimensions")
            if has_items: status_str.append("items")

            coverage = ", ".join(status_str) if status_str else "NO GROUND TRUTH"
            print(f"  {f.name:15s} -> [{coverage}]")
        print()


if __name__ == "__main__":
    main()
