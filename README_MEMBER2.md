# HNX26EPS06 — MEMBER 2: Geometry Validation, Topology Repair & Normalization Pipeline

## Overview

In the 4-person hackathon architecture for **Problem Statement 06 (Floor Plan → 3D Model)**, the team pipeline is structured as:

```
Member 1 (AI / Blueprint Segmentation)
           ↓
       scene.json (RAW image/pixel format)
           ↓
MEMBER 2 (Geometry Validation & Topology Repair)
  • Structural & Relational Validation
  • Topology Cleanup & Endpoint Snapping
  • Door / Window Explicit Geometry Resolution
  • Room Polygon Validation & Metric Analysis
  • Scale Handling (never invents measurements)
  • Source Provenance Preservation
           ↓
   validated_scene.json + validation_report.json + geometry_preview.png
           ↓
Member 3 (3D Mesh & GLB Generation)
           ↓
       scene.glb
           ↓
Member 4 / Viewer (Navigable 3D WebGL Presentation)
```

Member 2 is the **engineering bridge** between AI segmentation and 3D modeling: taking noisy raw segmentation data, detecting geometric defects, performing topology snapping, computing explicit opening geometries, preserving complete source traceability, and handing off a clean, structured `validated_scene.json` to Member 3.

---

## Forensic Analysis of Member 1's Raw `scene.json`

### 1. What Was Already Good
- **Valid JSON Structure**: Contains 14 walls, 4 doors, 4 windows, and 3 rooms.
- **Valid Room Polygons**: Room 1 (10 vertices, 46,465 px²), Room 2 (4 vertices, 5,692 px²), and Room 3 (4 vertices, 23,001 px²) have valid, non-self-intersecting topology.
- **Valid Referencing**: All 4 doors and 4 windows reference existing wall IDs (`w8`, `w10`, `w11`, `w14`, `w3`, `w2`, `w5`).

### 2. Geometry Defects & Anomalies Identified
1. **Suspicious Short Wall**:
   - `w9` has length of only **12.00 px** (`start=[72.0, 150.0]`, `end=[84.0, 150.0]`, `thickness=4.0`). It is an isolated stub segment.
2. **Disconnected / Isolated Walls**:
   - Walls `w3`, `w6`, `w8`, and `w9` have endpoints that do not meet any adjacent wall within standard connectivity thresholds.
3. **Extreme Boundary Opening Positions**:
   - `d1` on `w8` is at `position = 1.0` (extreme end of wall).
   - `d2` on `w10` is at `position = 0.0` (extreme start of wall).
   - `d3` on `w11` is at `position = 0.0` (extreme start of wall).
   - `d4` on `w14` is at `position = 1.0` (extreme end of wall).
   - `win1` and `win2` are both hosted on `w3` at positions `1.0` and `0.0`.
4. **Openings Exceeding Host Wall Length**:
   - Door `d3` has `width = 30.0 px`, while wall `w11` has length **29.07 px**.
   - Window `win3` has `width = 69.0 px`, while wall `w2` has length **54.06 px**.
5. **Endpoint Gaps**:
   - `w10.end` at `(373.0, 219.0)` and `w14.end` at `(359.0, 219.0)` lie on the exact same horizontal coordinate line `y = 219.0` with a 14.0 px gap.
6. **Scale Undefined**:
   - `scale.value = null`, `scale.source = "unknown"`, `scale.confidence = 0.0`.

### 3. What Member 2 Cleans & Normalizes
1. **Reports Anomalies without Destructive Deletion**: Issues are logged with severity (`error` vs `warning`) in `validation_report.json`.
2. **Endpoint Snapping**: Snaps endpoints within `WALL_SNAP_TOLERANCE` (e.g. 15 px) to mutual centroids, while preventing same-wall endpoints from collapsing into points.
3. **Explicit Opening Geometry**: Translates parametric `position: 0.5` into absolute 2D `center`, `start`, `end`, and `offset_from_start` coordinates.
4. **Source Provenance**: Every entity maintains a `source` block alongside its clean `geometry` block.
5. **No Measurement Fabrication**: If scale is unknown, units remain `pixels` and scale is annotated as unavailable. If `--scale <m_per_px>` is supplied, all metrics are mathematically converted.

---

## Output Contract for Member 3 (`validated_scene.json`)

```json
{
  "version": "1.0",
  "units": "pixels",
  "coordinate_system": "image",
  "image": {
    "width": 512,
    "height": 260
  },
  "scale": {
    "meters_per_pixel": null,
    "source": "unknown",
    "confidence": 0.0,
    "metric_available": false
  },
  "defaults": {
    "wall_height": 3.0,
    "door_height": 2.1,
    "window_sill_height": 0.9,
    "window_height": 1.2
  },
  "walls": [
    {
      "id": "w1",
      "source": {
        "start": [238.0, 18.0],
        "end": [79.5, 19.0],
        "thickness": 16.0
      },
      "geometry": {
        "start": [238.0, 18.0],
        "end": [79.5, 19.0],
        "thickness": 16.0,
        "length": 158.5
      },
      "start": [238.0, 18.0],
      "end": [79.5, 19.0],
      "thickness": 16.0
    }
  ],
  "doors": [
    {
      "id": "d1",
      "wall_id": "w8",
      "source": { "position": 1.0, "width": 24.0 },
      "geometry": {
        "center": [343.9, 146.2],
        "start": [331.91, 145.67],
        "end": [355.89, 146.73],
        "width": 24.0,
        "offset_from_start": 37.95
      },
      "position": 1.0,
      "width": 24.0
    }
  ],
  "windows": [ ... ],
  "rooms": [
    {
      "id": "room1",
      "label": "room1",
      "source": { "polygon": [...] },
      "geometry": {
        "polygon": [...],
        "area": 46465.0,
        "perimeter": 858.0,
        "bounds": [85.0, 27.0, 371.0, 214.0],
        "centroid": [223.3, 116.8],
        "num_vertices": 10
      },
      "polygon": [...]
    }
  ],
  "topology_operations": [
    {
      "type": "snap_endpoint",
      "wall_id": "w10",
      "endpoint": "end",
      "original": [373.0, 219.0],
      "snapped": [366.0, 219.0],
      "distance": 7.0
    }
  ],
  "validation": {
    "valid": true,
    "issues": [ ... ]
  }
}
```

---

## How to Run Member 2

Ensure the virtual environment is active:

```powershell
# 1. Process scene with unknown scale (safe default: preserves pixels)
.\.venv\Scripts\python.exe scripts/process_scene.py scene.json

# 2. Process scene with known scale (e.g. 0.02 meters/pixel)
.\.venv\Scripts\python.exe scripts/process_scene.py scene.json --scale 0.02

# 3. Process scene estimating scale from a known measurement (e.g. 100px = 2.0m)
.\.venv\Scripts\python.exe scripts/process_scene.py scene.json --reference 100.0 2.0

# 4. Custom output directory and snapping tolerance
.\.venv\Scripts\python.exe scripts/process_scene.py scene.json --outdir my_output --snap-tol 12.0
```

### Generated Output Files
All outputs are written to `geometry_output/`:
- `geometry_output/validated_scene.json`: Clean, normalized scene for Member 3.
- `geometry_output/validation_report.json`: Comprehensive report listing all geometric and topological findings.
- `geometry_output/geometry_preview.png`: High-resolution 2D CAD visual preview with original vs cleaned walls, doors, windows, room fills, and labels.

---

## Running the Automated Test Suite

Run the full pytest suite (24 tests):

```powershell
.\.venv\Scripts\pytest.exe -v
```

### Test Coverage
- `test_1_valid_wall`: Validates well-formed wall definitions.
- `test_2_invalid_wall`: Rejects missing fields, negative thickness, non-numeric coordinates.
- `test_3_missing_wall_reference`: Catches doors and windows referencing non-existent wall IDs.
- `test_4_invalid_door`: Catches negative door widths and out-of-bounds parametric positions.
- `test_5_invalid_window`: Catches negative window widths and invalid positions.
- `test_6_duplicate_wall`: Detects collinear/identical duplicate wall segments.
- `test_7_short_wall`: Flags suspicious walls shorter than `MIN_WALL_LENGTH`.
- `test_8_nearly_touching_walls`: Verifies endpoint clustering and snapping within tolerance.
- `test_9_valid_room_polygon`: Verifies area, perimeter, and bounding box computation.
- `test_10_invalid_room_polygon`: Catches polygons with < 3 points or non-numeric points.
- `test_11_known_scale_conversion`: Verifies mathematical conversion from pixels to meters.
- `test_12_unknown_scale_behavior`: Ensures unscaled scenes preserve pixel units without fabricating metrics.
- Plus 12 3D volumetric tests covering GLB/OBJ/PLY generation.

---

## Project Structure

```
├── geometry/
│   ├── __init__.py
│   ├── config.py              # Snapping and merging tolerances
│   ├── validator.py           # Deep structural and topological validation
│   ├── topology.py            # Endpoint snapping, gap detection, provenance
│   ├── openings.py            # Door and window 2D geometry resolution
│   ├── rooms.py               # Room polygon metrics and validation
│   ├── scale.py               # Pixel -> meter conversion & reference estimation
│   ├── normalize.py           # Pipeline orchestrator
│   └── visualize.py           # Matplotlib geometry preview generator
├── scripts/
│   └── process_scene.py       # Master CLI runner
├── tests/
│   ├── test_member2_pipeline.py # 12 core Phase 12 validation tests
│   └── test_geometry.py       # 3D volumetric generation tests
├── geometry_output/           # Output artifacts
│   ├── validated_scene.json
│   ├── validation_report.json
│   └── geometry_preview.png
├── scene.json                 # Member 1 raw input
├── requirements.txt           # Dependencies
└── pyproject.toml             # Configuration
```
