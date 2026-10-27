"""Export engine for standard watertight GLB/glTF 3D architectural scenes."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, Optional, Union

import trimesh

from src.models import FloorPlan


class GLBSceneExporter:
    """
    Exports watertight procedural 3D scenes to binary GLB and glTF formats.
    Includes materials, vertex colors, hierarchy, and architectural metadata.
    """

    def export(
        self,
        scene: trimesh.Scene,
        out_path: Union[str, Path],
        floor_plan: Optional[FloorPlan] = None,
    ) -> Path:
        """Exports trimesh.Scene to .glb file with companion JSON summary."""
        target_path = Path(out_path)
        target_path.parent.mkdir(parents=True, exist_ok=True)

        if target_path.suffix.lower() not in (".glb", ".gltf"):
            target_path = target_path.with_suffix(".glb")

        # Ensure all geometries have computed vertex normals for standard lighting
        for geom in scene.geometry.values():
            if hasattr(geom, "vertex_normals"):
                _ = geom.vertex_normals

        # Export binary GLB
        glb_bytes = scene.export(file_type="glb")
        with open(target_path, "wb") as f:
            f.write(glb_bytes)

        # Export companion architectural metadata JSON
        stats_path = target_path.with_name(f"{target_path.stem}_metadata.json")
        summary_data: Dict[str, Any] = {
            "file": target_path.name,
            "file_size_bytes": target_path.stat().st_size,
            "scene_metrics": dict(scene.metadata),
        }

        if floor_plan is not None:
            summary_data["floor_plan"] = floor_plan.to_dict()

        with open(stats_path, "w", encoding="utf-8") as f:
            json.dump(summary_data, f, indent=2)

        return target_path
