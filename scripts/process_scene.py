#!/usr/bin/env python3
"""
Member 2 Master Processing Script.

Processes raw scene.json from Member 1 into clean, validated, topology-repaired
validated_scene.json ready for direct consumption by Member 3.

Usage:
    python scripts/process_scene.py scene.json
    python scripts/process_scene.py scene.json --scale 0.02
    python scripts/process_scene.py scene.json --outdir custom_output
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from geometry.normalize import normalize_scene
from geometry.visualize import generate_preview
from geometry.scale import estimate_scale_from_reference
from geometry.config import WALL_SNAP_TOLERANCE, CORNER_SNAP_TOLERANCE


def main():
    parser = argparse.ArgumentParser(
        description="Member 2: Geometry Validation, Topology Repair & Normalization Pipeline"
    )
    parser.add_argument("input_scene", help="Path to raw scene.json from Member 1")
    parser.add_argument(
        "--scale", "-s",
        type=float,
        default=None,
        help="Optional known scale in meters_per_pixel (e.g. 0.02). If omitted, preserves pixel units without fabrication."
    )
    parser.add_argument(
        "--reference", "-r",
        nargs=2,
        type=float,
        metavar=("PIXELS", "METERS"),
        help="Estimate scale from reference length: e.g. --reference 100.0 2.5"
    )
    parser.add_argument(
        "--outdir", "-o",
        type=str,
        default="geometry_output",
        help="Output directory (default: geometry_output)"
    )
    parser.add_argument(
        "--snap-tol",
        type=float,
        default=WALL_SNAP_TOLERANCE,
        help=f"Endpoint snapping tolerance in pixels (default: {WALL_SNAP_TOLERANCE})"
    )

    args = parser.parse_args()

    input_path = Path(args.input_scene).resolve()
    if not input_path.exists():
        print(f"[ERROR] Input scene file not found: {input_path}", file=sys.stderr)
        sys.exit(1)

    print(f"\n=======================================================")
    print(f"  MEMBER 2: GEOMETRY PROCESSING & VALIDATION PIPELINE")
    print(f"  Input: {input_path.name}")
    print(f"=======================================================")

    try:
        with open(input_path, "r", encoding="utf-8") as f:
            raw_scene = json.load(f)
    except Exception as e:
        print(f"[ERROR] Failed to read JSON from '{input_path}': {e}", file=sys.stderr)
        sys.exit(1)

    # Determine scale factor
    meters_per_pixel = args.scale
    scale_source = "explicit" if meters_per_pixel else "unknown"
    scale_conf = 1.0 if meters_per_pixel else 0.0

    if args.reference:
        px_len, m_len = args.reference
        meters_per_pixel = estimate_scale_from_reference(px_len, m_len)
        scale_source = "reference_measurement"
        scale_conf = 0.95
        print(f"[*] Scale estimated from reference: {meters_per_pixel:.6f} m/px ({px_len}px = {m_len}m)")
    elif meters_per_pixel:
        print(f"[*] Known scale supplied: {meters_per_pixel:.6f} meters/pixel")
    else:
        print("[*] Scale unknown: preserving exact pixel coordinates without fabrication.")

    # Run normalization pipeline
    print("[*] Executing validation and topology cleanup...")
    normalized_scene, report = normalize_scene(
        raw_scene=raw_scene,
        meters_per_pixel=meters_per_pixel,
        scale_source=scale_source,
        scale_confidence=scale_conf,
        snap_tol=args.snap_tol,
    )

    # Prepare output directory
    out_dir = Path(args.outdir).resolve()
    out_dir.mkdir(parents=True, exist_ok=True)

    val_scene_file = out_dir / "validated_scene.json"
    val_report_file = out_dir / "validation_report.json"
    preview_file = out_dir / "geometry_preview.png"

    # Write validated_scene.json
    with open(val_scene_file, "w", encoding="utf-8") as f:
        json.dump(normalized_scene, f, indent=2)
    print(f"[OK] Saved: {val_scene_file}")

    # Write validation_report.json
    with open(val_report_file, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2)
    print(f"[OK] Saved: {val_report_file}")

    # Generate preview image
    print("[*] Generating visual geometry preview...")
    generate_preview(raw_scene, normalized_scene, str(preview_file))
    print(f"[OK] Saved: {preview_file}")

    # Print summary
    print("\n--- SUMMARY REPORT ---")
    print(f"  Valid: {report['valid']}")
    print(f"  Walls: {report['stats']['wall_count']}")
    print(f"  Doors: {report['stats']['door_count']}")
    print(f"  Windows: {report['stats']['window_count']}")
    print(f"  Rooms: {report['stats']['room_count']}")
    print(f"  Topology Snaps: {len(normalized_scene.get('topology_operations', []))}")
    print(f"  Issues Found: {len(report['issues'])} ({report['stats'].get('error_count', 0)} errors, {report['stats'].get('warning_count', 0)} warnings)")

    if report["issues"]:
        print("\n--- NOTABLE ISSUES ---")
        for iss in report["issues"][:8]:  # Print first 8
            icon = "[ERROR]" if iss["severity"] == "error" else "[WARN]"
            print(f"  {icon} [{iss['type']}] {iss['element_type']} '{iss['element_id']}': {iss['message']}")
        if len(report["issues"]) > 8:
            print(f"  ... and {len(report['issues']) - 8} more issues (see validation_report.json)")

    print("\n[SUCCESS] Ready for Member 3 handoff.\n")
    return 0 if report["valid"] else 1


if __name__ == "__main__":
    sys.exit(main())
