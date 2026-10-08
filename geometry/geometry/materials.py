"""
Professional architectural material presets for 3D scene generation.

Provides clean, neutral PBR materials suitable for BIM / CAD visualization.
"""

from __future__ import annotations

import trimesh
from trimesh.visual.material import PBRMaterial


class ArchitecturalMaterials:
    """Standard neutral architectural materials."""

    @staticmethod
    def wall_material() -> PBRMaterial:
        return PBRMaterial(
            name="Mat_Wall",
            baseColorFactor=[0.90, 0.89, 0.87, 1.0],  # Soft warm off-white plaster
            roughnessFactor=0.85,
            metallicFactor=0.0
        )

    @staticmethod
    def floor_material() -> PBRMaterial:
        return PBRMaterial(
            name="Mat_Floor",
            baseColorFactor=[0.78, 0.74, 0.68, 1.0],  # Architectural warm stone/wood tone
            roughnessFactor=0.6,
            metallicFactor=0.0
        )

    @staticmethod
    def ceiling_material() -> PBRMaterial:
        return PBRMaterial(
            name="Mat_Ceiling",
            baseColorFactor=[0.96, 0.96, 0.96, 1.0],  # Clean white ceiling plaster
            roughnessFactor=0.9,
            metallicFactor=0.0
        )

    @staticmethod
    def door_frame_material() -> PBRMaterial:
        return PBRMaterial(
            name="Mat_DoorFrame",
            baseColorFactor=[0.35, 0.25, 0.18, 1.0],  # Dark timber frame
            roughnessFactor=0.5,
            metallicFactor=0.05
        )

    @staticmethod
    def door_leaf_material() -> PBRMaterial:
        return PBRMaterial(
            name="Mat_DoorLeaf",
            baseColorFactor=[0.55, 0.38, 0.25, 1.0],  # Warm architectural wood
            roughnessFactor=0.45,
            metallicFactor=0.02
        )

    @staticmethod
    def window_frame_material() -> PBRMaterial:
        return PBRMaterial(
            name="Mat_WindowFrame",
            baseColorFactor=[0.22, 0.24, 0.26, 1.0],  # Anthracite architectural aluminum
            roughnessFactor=0.35,
            metallicFactor=0.4
        )

    @staticmethod
    def window_glass_material() -> PBRMaterial:
        return PBRMaterial(
            name="Mat_WindowGlass",
            baseColorFactor=[0.65, 0.85, 0.95, 0.35], # Translucent tinted glass
            roughnessFactor=0.05,
            metallicFactor=0.1,
            alphaMode="BLEND"
        )
