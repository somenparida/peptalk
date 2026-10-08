import os
import time
import json
import logging
from pathlib import Path
from typing import Dict, Any, Optional
import numpy as np
from PIL import Image

from .validators import validate_input, validate_scene
from .adapters import load_ai, load_geometry, load_3d, sanitize_mask
from .scale import calibrate_scale, apply_scale
from .schemas import Scene, validate_against_schema
from .config import OUTPUTS_DIR
from evaluation.baseline import baseline_geometry

log = logging.getLogger(__name__)


def reconstruct(
    input_path: Path | str,
    out_root: Path | str = OUTPUTS_DIR,
    mode: str = "proposed"
) -> Dict[str, Any]:
    """
    End-to-end reconstruction pipeline.
    mode: 'proposed' (with scale calibration & topology repair) or 'baseline'
    Returns dict: {"scene": scene_dict, "glb": glb_path_str, "report": report_dict}
    """
    t_start = time.time()
    input_path = Path(input_path).resolve()
    out_root = Path(out_root).resolve()

    plan_name = input_path.stem
    run_dir = out_root / plan_name
    run_dir.mkdir(parents=True, exist_ok=True)

    report: Dict[str, Any] = {
        "input": input_path.name,
        "mode": mode,
        "status": "in_progress",
        "implementations": {},
        "timings_s": {},
        "components": {},
        "scale": {},
        "validation": {},
        "geometry_counters": {},
        "output": {},
    }

    try:
        # Step 1: Input Validation
        log.info("[1/6] Validating input: %s", input_path.name)
        usable_img_path, input_warnings = validate_input(input_path)

        # Handle direct JSON blueprint scene input from Member 1
        if input_path.suffix.lower() == ".json":
            log.info("Processing direct Member 1 scene.json input...")
            with open(usable_img_path, "r", encoding="utf-8") as f:
                scene_raw = json.load(f)

            report["implementations"] = {"ai": "member1_json", "geometry": "real", "3d": "real"}

            # Calibrate scale if in pixel units or scale is uncalibrated
            if scene_raw.get("units") == "pixels" or "scale" not in scene_raw:
                mpp, src, conf, c_warns = calibrate_scale(scene_raw)
                scene_m, a_warns = apply_scale(scene_raw, mpp, scale_source=src, confidence=conf)
                scale_warns = c_warns + a_warns
            else:
                scene_m = scene_raw

            report["scale"] = scene_m.get("scale", {})

            # Validate scene topology
            is_valid, errors, val_warnings, counters = validate_scene(scene_m)
            all_warnings = input_warnings + scale_warns + val_warnings

            report["validation"] = {"valid": is_valid, "errors": errors, "warnings": all_warnings}
            report["geometry_counters"] = counters
            report["components"] = {
                "walls": len(scene_m.get("walls", [])),
                "doors": len(scene_m.get("doors", [])),
                "windows": len(scene_m.get("windows", [])),
                "rooms": len(scene_m.get("rooms", [])),
            }

            scene_json_path = run_dir / "scene.json"
            with open(scene_json_path, "w", encoding="utf-8") as f:
                json.dump(scene_m, f, indent=2)

            # Export 3D GLB model
            glb_dest = run_dir / "scene.glb"
            export_3d_func, export_impl = load_3d()
            export_3d_func(scene_m, glb_dest)

            def rel_path_str(p: Path) -> str:
                try:
                    return str(p.relative_to(OUTPUTS_DIR.parent))
                except ValueError:
                    return str(p)

            report["status"] = "success"
            report["timings_s"] = {"total": round(time.time() - t_start, 3)}
            report["output"] = {
                "scene": rel_path_str(scene_json_path),
                "model": rel_path_str(glb_dest),
                "report": rel_path_str(run_dir / "report.json"),
            }

            save_report(run_dir / "report.json", report)
            return {"scene": scene_m, "glb": str(glb_dest), "report": report}

        # Step 2: AI Segmentation
        t0 = time.time()
        ai_func, ai_impl = load_ai()
        report["implementations"]["ai"] = ai_impl
        log.info("[2/6] Running AI segmentation (%s)...", ai_impl)

        raw_masks = ai_func(usable_img_path)
        report["timings_s"]["ai"] = round(time.time() - t0, 3)

        # Sanitize and save debug mask images
        masks = {
            "wall_mask": sanitize_mask(raw_masks.get("wall_mask")),
            "door_mask": sanitize_mask(raw_masks.get("door_mask")),
            "window_mask": sanitize_mask(raw_masks.get("window_mask")),
            "floor_mask": sanitize_mask(raw_masks.get("floor_mask")),
        }

        Image.fromarray(masks["wall_mask"]).save(run_dir / "wall_mask.png")
        Image.fromarray(masks["door_mask"]).save(run_dir / "door_mask.png")
        Image.fromarray(masks["window_mask"]).save(run_dir / "window_mask.png")
        Image.fromarray(masks["floor_mask"]).save(run_dir / "floor_mask.png")

        if np.sum(masks["wall_mask"] > 0) == 0:
            raise ValueError(
                "No walls detected by AI segmentation. Saved debug masks to outputs folder."
            )

        # Step 3: Geometry Reconstruction
        t0 = time.time()
        if mode == "baseline":
            geom_impl = "baseline"
            log.info("[3/6] Running Geometry baseline engine...")
            scene_px = baseline_geometry(masks)
        else:
            geom_func, geom_impl = load_geometry()
            log.info("[3/6] Running Geometry reconstruction (%s)...", geom_impl)
            scene_px = geom_func(masks)

        report["implementations"]["geometry"] = geom_impl
        report["timings_s"]["geometry"] = round(time.time() - t0, 3)

        # Step 4: Scale Calibration & Application
        t0 = time.time()
        scale_warns = []
        if mode == "baseline" or scene_px.get("units") == "meters":
            scene_m = scene_px
            if "scale" not in scene_m:
                scene_m["scale"] = {
                    "value": 0.015,
                    "unit": "meters_per_pixel",
                    "source": "estimated",
                    "confidence": 0.3,
                }
        else:
            log.info("[4/6] Calibrating scale...")
            mpp, src, conf, c_warns = calibrate_scale(scene_px, usable_img_path)
            scene_m, a_warns = apply_scale(scene_px, mpp, scale_source=src, confidence=conf)
            scale_warns.extend(c_warns + a_warns)

        report["timings_s"]["scale"] = round(time.time() - t0, 3)
        report["scale"] = scene_m.get("scale", {})

        # Step 5: Scene Validation
        t0 = time.time()
        log.info("[5/6] Validating scene geometry...")
        is_valid, errors, val_warnings, counters = validate_scene(scene_m)
        all_warnings = input_warnings + scale_warns + val_warnings

        report["timings_s"]["validation"] = round(time.time() - t0, 3)
        report["validation"] = {
            "valid": is_valid,
            "errors": errors,
            "warnings": all_warnings,
        }
        report["geometry_counters"] = counters
        report["components"] = {
            "walls": len(scene_m.get("walls", [])),
            "doors": len(scene_m.get("doors", [])),
            "windows": len(scene_m.get("windows", [])),
            "rooms": len(scene_m.get("rooms", [])),
        }

        scene_json_path = run_dir / "scene.json"
        with open(scene_json_path, "w", encoding="utf-8") as f:
            json.dump(scene_m, f, indent=2)

        if not is_valid and errors:
            err_msg = "\n".join(errors)
            report["status"] = "failed"
            report["error"] = err_msg
            save_report(run_dir / "report.json", report)
            raise ValueError(f"Scene validation failed with errors:\n{err_msg}")

        # Step 6: 3D GLB Export
        t0 = time.time()
        export_3d_func, export_impl = load_3d()
        report["implementations"]["3d"] = export_impl
        glb_path = run_dir / "scene.glb"
        log.info("[6/6] Exporting 3D model (%s)...", export_impl)

        export_3d_func(scene_m, glb_path)
        report["timings_s"]["3d"] = round(time.time() - t0, 3)

        def rel_path_str(p: Path) -> str:
            try:
                return str(p.relative_to(OUTPUTS_DIR.parent))
            except ValueError:
                return str(p)

        report["status"] = "success"
        report["timings_s"]["total"] = round(time.time() - t_start, 3)
        report["output"] = {
            "scene": rel_path_str(scene_json_path),
            "model": rel_path_str(glb_path),
            "report": rel_path_str(run_dir / "report.json"),
        }

        save_report(run_dir / "report.json", report)
        log.info("Pipeline completed successfully in %.2fs", report["timings_s"]["total"])

        return {
            "scene": scene_m,
            "glb": str(glb_path),
            "report": report,
        }

    except Exception as e:
        log.error("Pipeline failure on %s: %s", input_path.name, e)
        report["status"] = "failed"
        report["error"] = str(e)
        report["timings_s"]["total"] = round(time.time() - t_start, 3)
        save_report(run_dir / "report.json", report)
        raise e


def save_report(path: Path, report: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2)
