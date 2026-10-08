"""
Command-Line Interface (CLI) for Member 2 3D Scene Generation Pipeline.

Commands:
  validate   Validate a scene.json file against schema and geometric rules.
  report     Generate and display a detailed dimension & accuracy report.
  generate   Build and export the 3D scene (GLB, GLTF, OBJ, PLY).
  view       Launch the interactive 3D web viewer with visual debug inspection.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from geometry.validator import SceneValidator
from geometry.adapter import SceneAdapter
from geometry.scene_graph import SceneGraph
from geometry.exporter import SceneExporter
from geometry.viewer.server import start_viewer


def cmd_validate(args: argparse.Namespace) -> int:
    path = Path(args.scene_file)
    if not path.exists():
        print(f"[ERROR] Scene file '{path}' does not exist.", file=sys.stderr)
        return 1

    try:
        with open(path, "r", encoding="utf-8") as f:
            raw_data = json.load(f)
    except Exception as e:
        print(f"[ERROR] Failed to read JSON from '{path}': {e}", file=sys.stderr)
        return 1

    # Check if adapter normalization requested
    if args.use_adapter:
        try:
            spec = SceneAdapter.normalize(raw_data)
            raw_data = spec.model_dump()
        except Exception as e:
            print(f"[ERROR] Adapter normalization failed: {e}", file=sys.stderr)
            return 1

    result = SceneValidator.validate_raw_json(raw_data)

    if not result.is_valid:
        print(f"\n[VALIDATION FAILED] {len(result.errors)} error(s) found in {path.name}:")
        for err in result.errors:
            print(f"  ❌ {err}")
        return 1

    print(f"\n[VALIDATION SUCCESS] {path.name} is a valid architectural scene!")
    print(f"  Rooms:   {result.report['rooms']['valid']}/{result.report['rooms']['total']}")
    print(f"  Walls:   {result.report['walls']['valid']}/{result.report['walls']['total']}")
    print(f"  Doors:   {result.report['doors']['valid']}/{result.report['doors']['total']}")
    print(f"  Windows: {result.report['windows']['valid']}/{result.report['windows']['total']}")
    print(f"  Total Floor Area: {result.report['total_floor_area_m2']:.2f} m²")
    if result.warnings:
        print(f"  Warnings ({len(result.warnings)}):")
        for w in result.warnings:
            print(f"    ⚠️  {w}")
    return 0


def cmd_report(args: argparse.Namespace) -> int:
    path = Path(args.scene_file)
    if not path.exists():
        print(f"[ERROR] Scene file '{path}' does not exist.", file=sys.stderr)
        return 1

    with open(path, "r", encoding="utf-8") as f:
        raw_data = json.load(f)

    result = SceneValidator.validate_raw_json(raw_data)
    rep = result.report

    if not result.is_valid:
        print(f"\n[SCENE INVALID] Cannot generate full accuracy report:")
        for err in result.errors:
            print(f"  ❌ {err}")
        return 1

    print("\n" + "=" * 65)
    print(f"     ARCHITECTURAL DIMENSION & ACCURACY REPORT")
    print(f"     Source File: {path.name}")
    print("=" * 65)
    print(f"Coordinate System: Up-Axis=Z, Horizontal=[X, Y] (Units: {rep['units']})")
    print(f"Wall Height (Default): {rep['wall_height_default']}m")
    print(f"Total Floor Area:      {rep['total_floor_area_m2']} m²\n")

    print("--- ROOM METRICS ---")
    for r in rep["rooms"]["details"]:
        print(f"  • [{r['id']}] {r['name']}: Area = {r['area_m2']} m² | Perimeter = {r['perimeter_m']} m | Bounds = {r['bounding_box']}")

    print("\n--- WALL METRICS ---")
    for w in rep["walls"]["details"]:
        print(f"  • [{w['id']}]: Length = {w['length_m']}m | Thickness = {w['thickness_m']}m | Height = {w['height_m']}m | Angle = {w['orientation_deg']}°")

    print("\n--- DOOR METRICS ---")
    for d in rep["doors"]["details"]:
        print(f"  • [{d['id']}]: Wall = {d['wall_id']} | Offset = {d['offset_m']}m | Width = {d['width_m']}m | Height = {d['height_m']}m")

    print("\n--- WINDOW METRICS ---")
    for win in rep["windows"]["details"]:
        print(f"  • [{win['id']}]: Wall = {win['wall_id']} | Offset = {win['offset_m']}m | Width = {win['width_m']}m | Height = {win['height_m']}m | Sill = {win['sill_height_m']}m")

    print("=" * 65 + "\n")
    return 0


def cmd_generate(args: argparse.Namespace) -> int:
    path = Path(args.scene_file)
    if not path.exists():
        print(f"[ERROR] Scene file '{path}' does not exist.", file=sys.stderr)
        return 1

    with open(path, "r", encoding="utf-8") as f:
        raw_data = json.load(f)

    if args.use_adapter:
        raw_data = SceneAdapter.normalize(raw_data).model_dump()

    v_res = SceneValidator.validate_raw_json(raw_data)
    if not v_res.is_valid:
        print(f"[ERROR] Validation failed for '{path.name}':", file=sys.stderr)
        for err in v_res.errors:
            print(f"  - {err}", file=sys.stderr)
        return 1

    output_path = Path(args.output) if args.output else path.with_suffix(f".{args.format}")

    print(f"Constructing 3D scene graph for {path.name}...")
    sg = SceneGraph.from_specification(
        spec=v_res.spec,
        build_accessories=not args.no_accessories
    )

    print(f"Exporting scene to {output_path} (format: {args.format})...")
    final_path = SceneExporter.export(
        scene_graph=sg,
        output_path=output_path,
        file_format=args.format
    )

    size_kb = final_path.stat().st_size / 1024.0
    print(f"\n[GENERATION COMPLETE]")
    print(f"  Output: {final_path}")
    print(f"  Size:   {size_kb:.1f} KB")
    print(f"  Nodes:  {len(sg.nodes)} architectural entities")
    return 0


def cmd_view(args: argparse.Namespace) -> int:
    path = Path(args.scene_file)
    if not path.exists():
        print(f"[ERROR] Scene file '{path}' does not exist.", file=sys.stderr)
        return 1

    start_viewer(
        scene_path=path,
        port=args.port,
        open_browser=not args.no_browser
    )
    return 0


def main():
    parser = argparse.ArgumentParser(
        prog="scene-gen",
        description="HNX26EPS06 Member 2: 3D Scene Generation from Blueprints"
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    # validate
    p_val = subparsers.add_parser("validate", help="Validate a scene.json file")
    p_val.add_argument("scene_file", help="Path to scene.json")
    p_val.add_argument("--use-adapter", action="store_true", help="Run through adapter to normalize external schemas")
    p_val.set_defaults(func=cmd_validate)

    # report
    p_rep = subparsers.add_parser("report", help="Display dimension and accuracy report")
    p_rep.add_argument("scene_file", help="Path to scene.json")
    p_rep.set_defaults(func=cmd_report)

    # generate
    p_gen = subparsers.add_parser("generate", help="Generate 3D model and export to file")
    p_gen.add_argument("scene_file", help="Path to scene.json")
    p_gen.add_argument("-o", "--output", help="Output file path (default: same name as scene)")
    p_gen.add_argument("-f", "--format", choices=["glb", "gltf", "obj", "ply"], default="glb", help="Export format (default: glb)")
    p_gen.add_argument("--no-accessories", action="store_true", help="Omit door leaves and window glass frames")
    p_gen.add_argument("--use-adapter", action="store_true", help="Run through adapter to normalize external schemas")
    p_gen.set_defaults(func=cmd_generate)

    # view
    p_view = subparsers.add_parser("view", help="Launch interactive 3D web viewer")
    p_view.add_argument("scene_file", help="Path to scene.json")
    p_view.add_argument("-p", "--port", type=int, default=8080, help="Viewer HTTP port (default: 8080)")
    p_view.add_argument("--no-browser", action="store_true", help="Do not automatically open browser")
    p_view.set_defaults(func=cmd_view)

    args = parser.parse_args()
    sys.exit(args.func(args))


if __name__ == "__main__":
    main()
