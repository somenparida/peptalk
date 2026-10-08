# HNX26EPS06 Floor Plan Dataset

This directory contains training, development, held-out evaluation, and demo floor plan datasets.

## Dataset Structure

```text
data/
├── development/      # plan_01.png .. plan_06.png (development & hyperparameter tuning)
├── heldout/          # plan_07.png .. plan_10.png (held-out benchmark evaluation ONLY)
├── demo/             # demo_01.png (simple), demo_02.png (medium), demo_03.png (messy)
├── expected/         # Ground truth JSON files per plan (<plan_name>.json)
├── masks/            # Optional ground truth wall/room masks
└── README.md
```

## Ground Truth JSON Schema

Ground truth annotations follow the structure below. Fields with missing annotations are set to `null` to avoid fabricating ground truth.

```json
{
  "plan": "plan_07",
  "counts": { "walls": 18, "doors": 7, "windows": 11, "rooms": 6 },
  "building_width_m": 12.5,
  "building_length_m": 9.2,
  "items": {
    "doors": [{"center_m": [3.2, 0.0]}],
    "windows": [{"center_m": [6.0, 9.2]}]
  },
  "masks": { "wall": "data/masks/plan_07_wall.png" }
}
```
