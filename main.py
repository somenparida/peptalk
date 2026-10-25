"""HNX26EPS06: 3D Scene Generation from Blueprints (Mode A).

Master CLI Entrypoint:
  python main.py process <floorplan_path> [--scale <m_per_px>] [--outdir <dir>] [--view]
  python main.py view [--glb <path>] [--port <port>]
  python main.py test
  python main.py benchmark [--outdir <dir>]
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from src.builder.scene_builder import ArchitecturalSceneBuilder
from src.exporter.glb_exporter import GLBSceneExporter
from src.parser.pipeline import FloorPlanParserPipeline
from src.parser.synthetic_generator import SyntheticBenchmarkGenerator
from src.viewer.server import start_viewer_server


def cmd_process(args: argparse.Namespace) -> None:
    input_path = Path(args.floorplan_path)
    if not input_path.exists():
        print(f"Error: Floor plan file not found: {input_path}", file=sys.stderr)
        sys.exit(1)

    out_dir = Path(args.outdir) if args.outdir else Path("output")
    out_dir.mkdir(parents=True, exist_ok=True)

    print("=" * 60)
    print(" HNX26EPS06: 3D SCENE GENERATION FROM BLUEPRINT")
    print(f" Input:  {input_path}")
    print(f" Output: {out_dir}")
    if args.scale:
        print(f" Manual Scale: {args.scale:.5f} m/pixel")
    print("=" * 60)

    # 1. Parse Floor Plan & Run Stage 1 & Stage 2 Geometry Cleanup
    print("\n[Stage 1 & 2] Ingesting blueprint and executing geometric cleanup...")
    pipeline = FloorPlanParserPipeline()
    floor_plan = pipeline.parse(input_path, scale=args.scale)

    # Display 3-Tier Validation Report
    report = floor_plan.validation
    print(f"\n--- Validation Report (3-Tier Audit) ---")
    print(f"Status:   {'FAILED (ERRORS DETECTED)' if report.has_errors else 'PASSED'}")
    print(f"Errors:   {report.error_count}")
    print(f"Warnings: {report.warning_count}")
    print(f"Audit:    {report.info_count} info items")

    # Reconfigure stdout for UTF-8 on Windows
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

    for issue in report.issues:
        prefix = f"[{issue.level.value}]"
        if issue.level.value == "ERROR":
            print(f"  [ERROR] {prefix:10s} ({issue.code}) {issue.message}")
        elif issue.level.value == "WARNING":
            print(f"  [WARN]  {prefix:10s} ({issue.code}) {issue.message}")
        else:
            print(f"  [INFO]  {prefix:10s} ({issue.code}) {issue.message}")

    if report.has_errors:
        print("\n[ERROR] Blocking geometric errors encountered. Aborting 3D reconstruction.")
        sys.exit(1)

    # 2. Stage 3: Procedural 3D Mesh Reconstruction
    print("\n[Stage 3] Constructing procedural 3D watertight solid meshes...")
    scene_builder = ArchitecturalSceneBuilder()
    scene = scene_builder.build_scene(floor_plan)

    total_faces = sum(len(g.faces) for g in scene.geometry.values() if hasattr(g, "faces"))
    total_verts = sum(len(g.vertices) for g in scene.geometry.values() if hasattr(g, "vertices"))
    print(f"  Reconstructed {len(scene.geometry)} architectural component nodes.")
    print(f"  Total Vertices: {total_verts:,} | Total Triangular Faces: {total_faces:,}")

    # 3. Stage 4: GLB Export
    glb_filename = f"{input_path.stem}_scene.glb"
    glb_out_path = out_dir / glb_filename
    print(f"\n[Stage 4] Exporting watertight 3D GLB to: {glb_out_path}")
    exporter = GLBSceneExporter()
    exported_file = exporter.export(scene, glb_out_path, floor_plan=floor_plan)

    print(f"  Export successful! File size: {exported_file.stat().st_size / 1024:.1f} KB")
    print(f"  Companion metadata: {exported_file.with_name(f'{exported_file.stem}_metadata.json')}")

    # Also copy or link to viewer default location for immediate inspection
    default_viewer_glb = Path("src/viewer/web/scene.glb")
    default_viewer_glb.parent.mkdir(parents=True, exist_ok=True)
    with open(exported_file, "rb") as src, open(default_viewer_glb, "wb") as dst:
        dst.write(src.read())

    meta_file = exported_file.with_name(f"{exported_file.stem}_metadata.json")
    if meta_file.exists():
        default_viewer_meta = Path("src/viewer/web/metadata.json")
        with open(meta_file, "rb") as src, open(default_viewer_meta, "wb") as dst:
            dst.write(src.read())

    # Optional Viewer Launch
    if args.view:
        print("\n[Viewer] Launching interactive 3D Web Viewer...")
        start_viewer_server(glb_path=exported_file, port=args.port, open_browser=True, block=True)


def cmd_view(args: argparse.Namespace) -> None:
    glb_target = args.glb
    if not glb_target:
        # Check standard output locations: prioritize most recently processed scene
        candidates = [
            Path("src/viewer/web/scene.glb"),
            Path("output/benchmark_ground_truth_scene.glb"),
            Path("output/benchmark_floorplan_scene.glb"),
        ]
        for candidate in candidates:
            if candidate.exists():
                glb_target = str(candidate)
                break
        if not glb_target:
            glb_target = "src/viewer/web/scene.glb"

    start_viewer_server(glb_path=glb_target, port=args.port, open_browser=True, block=True)


def cmd_test(args: argparse.Namespace) -> None:
    import pytest

    pytest_args = ["-v", "tests"]
    print("Running automated test suite via pytest...")
    sys.exit(pytest.main(pytest_args))


def cmd_benchmark(args: argparse.Namespace) -> None:
    out_dir = Path(args.outdir) if args.outdir else Path("data/benchmark")
    print(f"Generating synthetic benchmark floor plans to: {out_dir}")
    gen = SyntheticBenchmarkGenerator(pixels_per_meter=50.0)
    img_path, json_path = gen.export_benchmark_dataset(out_dir)
    print(f"  Generated Blueprint Image: {img_path}")
    print(f"  Generated Ground Truth:   {json_path}")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="HNX26EPS06: 3D Scene Generation from Blueprints (Mode A)"
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    # Process command
    proc_parser = subparsers.add_parser("process", help="Process floor plan image/JSON to 3D GLB")
    proc_parser.add_argument("floorplan_path", help="Path to blueprint image (PNG, JPG) or JSON spec")
    proc_parser.add_argument("--scale", type=float, default=None, help="Scale calibration (meters per pixel)")
    proc_parser.add_argument("--outdir", default="output", help="Directory for exported 3D scenes")
    proc_parser.add_argument("--view", action="store_true", help="Launch interactive 3D viewer upon completion")
    proc_parser.add_argument("--port", type=int, default=8080, help="Viewer HTTP port")

    # View command
    view_parser = subparsers.add_parser("view", help="Launch interactive Three.js 3D viewer")
    view_parser.add_argument("--glb", default=None, help="Path to GLB model file")
    view_parser.add_argument("--port", type=int, default=8080, help="Viewer HTTP port")

    # Test command
    subparsers.add_parser("test", help="Execute test suite")

    # Benchmark command
    bench_parser = subparsers.add_parser("benchmark", help="Generate synthetic ground-truth benchmark dataset")
    bench_parser.add_argument("--outdir", default="data/benchmark", help="Output directory")

    args = parser.parse_args()

    if args.command == "process":
        cmd_process(args)
    elif args.command == "view":
        cmd_view(args)
    elif args.command == "test":
        cmd_test(args)
    elif args.command == "benchmark":
        cmd_benchmark(args)


if __name__ == "__main__":
    main()
