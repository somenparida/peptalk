# Member 2 Handoff: Floor Plan Segmentation Masks

This directory contains the verified semantic segmentation masks produced by Member 1 (AI / Segmentation) for downstream 3D reconstruction and geometry vectorization (Member 2).

---

## Input
- **Source Image**: `test_floorplan.png` (from `data/input/test_floorplan.png`)
- **Dimensions**: 512 × 260 pixels

---

## Output Mask Files
- **`wall_mask.png`**: Binary mask containing all wall structures.
- **`door_mask.png`**: Binary mask containing door openings and thresholds.
- **`window_mask.png`**: Binary mask containing exterior and interior window openings.
- **`floor_mask.png`**: Binary mask containing the interior walkable room surfaces.

---

## Semantic Class Mapping Contract
The internal model taxonomy and class IDs are:

| Class ID | Class Name | Output Mask File | Description |
| :--- | :--- | :--- | :--- |
| **0** | `floor` | `floor_mask.png` | Interior rooms and negative space |
| **1** | `wall` | `wall_mask.png` | Structural load-bearing and interior walls |
| **2** | `door` | `door_mask.png` | Door openings (cutouts through walls) |
| **3** | `window` | `window_mask.png` | Window openings along wall segments |

---

## Mask Specifications & Guarantees
- **Format**: Standard 8-bit grayscale binary PNG (`uint8`).
  - Active class pixels = `255`
  - Inactive pixels = `0`
- **Resolution**: Exactly matches the **original input image dimensions** ($512 \times 260$).
- **Class Exclusivity**: Every pixel belongs to exactly one semantic class.
  - $\text{wall} + \text{door} + \text{window} + \text{floor} = \text{total image pixels}$.
  - Overlap across masks = 0 pixels.
  - Unclassified pixels = 0 pixels.
- **Aspect Ratio**: Perfectly preserved via letterbox preprocessing; no artificial stretching.

---

## Machine-Readable Metadata & Vectorized Scene
- **`metadata.json`**: Exact dimensions, class counts, and file references for segmentation masks.
- **`scene.json`**: Clean architectural vector representation with walls, doors, windows, and rooms extracted from the masks. Fully compatible with Member 2's `SceneAdapter` and 3D generation pipeline.

---

## Member 2 Usage Guide

Validate `scene.json` using Member 2's validation CLI:
```bash
python -m src.cli validate data/masks/scene.json --use-adapter
```

Generate 3D GLB model directly from `scene.json`:
```bash
python -m src.cli generate data/masks/scene.json --use-adapter -o output_scene.glb
```

