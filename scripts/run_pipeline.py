#!/usr/bin/env python3
import sys
import argparse
import logging
from pathlib import Path

# Add project root to sys.path
BASE_DIR = Path(__file__).resolve().parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from integration.pipeline import reconstruct
from integration.config import OUTPUTS_DIR


def main():
    parser = argparse.ArgumentParser(
        description="HNX26EPS06 — 3D Scene Generation Pipeline Runner"
    )
    parser.add_argument("input_path", type=str, help="Path to input floorplan (.png, .jpg, .jpeg, .pdf)")
    parser.add_argument("--baseline", action="store_true", help="Run naive baseline pipeline")
    parser.add_argument("--out", type=str, default=str(OUTPUTS_DIR), help="Output directory root")
    parser.add_argument("--verbose", action="store_true", help="Enable verbose logging")

    args = parser.parse_args()

    log_level = logging.DEBUG if args.verbose else logging.INFO
    logging.basicConfig(level=log_level, format="%(levelname)s: %(message)s")

    input_file = Path(args.input_path)
    mode = "baseline" if args.baseline else "proposed"

    print(f"\nProcessing {input_file.name} (mode: {mode})\n")

    try:
        res = reconstruct(input_path=input_file, out_root=args.out, mode=mode)
        report = res["report"]

        ai_impl = report["implementations"].get("ai", "unknown")
        geom_impl = report["implementations"].get("geometry", "unknown")
        export_impl = report["implementations"].get("3d", "unknown")

        scale_info = report.get("scale", {})
        scale_src = scale_info.get("source", "unknown")
        scale_conf = scale_info.get("confidence", 0.0)

        num_warns = len(report.get("validation", {}).get("warnings", []))

        print(f"[1/6] Preprocessing ........ OK")
        print(f"[2/6] AI segmentation ..... OK   ({ai_impl})")
        print(f"[3/6] Geometry ............ OK   ({geom_impl})")
        print(f"[4/6] Scale ............... OK   (source={scale_src}, conf={scale_conf:.2f})")
        print(f"[5/6] Validation .......... OK   ({num_warns} warnings)")
        print(f"[6/6] 3D export ........... OK   ({export_impl})")

        print("\nOutput:")
        print(f"{report['output']['scene']}")
        print(f"{report['output']['model']}")
        print(f"{report['output']['report']}\n")
        sys.exit(0)

    except Exception as e:
        print(f"\n[ERROR] Pipeline failed on {input_file.name}")
        print(f"Details: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
