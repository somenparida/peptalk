"""
3D Scene Exporter module for Member 2.

Exports the structured SceneGraph to standard 3D formats:
- GLB (Primary target: binary glTF 2.0 with full materials, node names, and hierarchy)
- GLTF (JSON glTF with embedded or separate buffers)
- OBJ (Wavefront OBJ with geometry)
- PLY (Polygon File Format)
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Literal, Union
import trimesh

from src.scene_graph import SceneGraph


SupportedFormat = Literal["glb", "gltf", "obj", "ply"]


class SceneExporter:
    """Exports SceneGraph instances to standard 3D file formats."""

    @staticmethod
    def export(
        scene_graph: SceneGraph,
        output_path: Union[str, Path],
        file_format: Optional[SupportedFormat] = None
    ) -> Path:
        """
        Exports scene graph to the specified path.
        If file_format is omitted, infers from output_path extension.
        Defaults to 'glb' if extension is not recognized.
        """
        out_path = Path(output_path).resolve()
        out_path.parent.mkdir(parents=True, exist_ok=True)

        if file_format is None:
            ext = out_path.suffix.lower().lstrip(".")
            if ext in ["glb", "gltf", "obj", "ply"]:
                file_format = ext  # type: ignore
            else:
                file_format = "glb"
                out_path = out_path.with_suffix(".glb")

        trimesh_scene = scene_graph.to_trimesh_scene()

        if file_format == "glb":
            data = trimesh_scene.export(file_type="glb")
            with open(out_path, "wb") as f:
                f.write(data)
        elif file_format == "gltf":
            data = trimesh_scene.export(file_type="gltf")
            if isinstance(data, (bytes, bytearray)):
                with open(out_path, "wb") as f:
                    f.write(data)
            else:
                with open(out_path, "w", encoding="utf-8") as f:
                    f.write(data)
        elif file_format == "obj":
            data = trimesh_scene.export(file_type="obj")
            if isinstance(data, (bytes, bytearray)):
                with open(out_path, "wb") as f:
                    f.write(data)
            else:
                with open(out_path, "w", encoding="utf-8") as f:
                    f.write(data)
        elif file_format == "ply":
            data = trimesh_scene.export(file_type="ply")
            with open(out_path, "wb") as f:
                f.write(data)
        else:
            raise ValueError(f"Unsupported export format '{file_format}'. Supported: glb, gltf, obj, ply")

        return out_path
