# HNX26EPS06 — MEMBER 2: 3D Scene Generation Pipeline

## Overview

This module implements **MEMBER 2 (Mode A)** of the competition problem:
> **"Take a 2D architectural blueprint / floor plan and generate a correctly scaled, navigable 3D representation of the space."**

While **Member 1** extracts structured 2D geometry from raw blueprints into a standardized representation (`scene.json`), **Member 2** consumes this structured representation and produces volumetric, physically accurate 3D geometry with true openings, multi-room topology, standard 3D export (GLB, OBJ, PLY), and an interactive 3D WebGL viewer with a real-time Visual Debug Inspector.

---

## Coordinate System Conventions

Member 2 enforces a single, mathematically consistent architectural coordinate system:

| Axis | Direction | Description |
| :--- | :--- | :--- |
| **+X** | Horizontal | Width / lateral plane |
| **+Y** | Depth | Length / longitudinal plane |
| **+Z** | Vertical (Up) | Elevation / wall height |

- **Metric Scale**: `1.0 unit = 1.0 meter` (strictly preserved; no silent scaling or normalization).
- **Ground / Floor Plane**: `z = 0.0m`.
- **Wall Elevation**: Extends upwards from `z = 0.0m` to `z = wall_height` (e.g. `2.8m` or `3.0m`).
- **Door Openings**: Void extends from `z = 0.0m` to `z = door.height` (e.g. `2.1m`). Solid lintel spans above the door to `wall_height`.
- **Window Openings**: Solid sill extends from `z = 0.0m` to `z = sill_height`. Void spans from `z = sill_height` to `z = sill_height + window.height`. Solid lintel spans above to `wall_height`.

---

## Member 1 ➔ Member 2 Interface Contract

The primary interface contract is the standardized `scene.json` file. A machine-readable JSON Schema is published at [`schemas/scene.schema.json`](schemas/scene.schema.json).

### `scene.json` Specification

```json
{
  "units": "meters",
  "coordinate_system": {
    "up_axis": "Z",
    "horizontal_axes": ["X", "Y"]
  },
  "wall_height": 2.8,

  "walls": [
    {
      "id": "wall_01",
      "start": [0.0, 0.0],
      "end": [5.2, 0.0],
      "thickness": 0.15,
      "height": 2.8
    }
  ],

  "doors": [
    {
      "id": "door_01",
      "wall_id": "wall_01",
      "offset": 2.1,
      "width": 0.9,
      "height": 2.1
    }
  ],

  "windows": [
    {
      "id": "window_01",
      "wall_id": "wall_01",
      "offset": 3.4,
      "width": 1.4,
      "height": 1.2,
      "sill_height": 0.9
    }
  ],

  "rooms": [
    {
      "id": "room_01",
      "name": "Living Room",
      "polygon": [
        [0.0, 0.0],
        [5.2, 0.0],
        [5.2, 4.8],
        [0.0, 4.8]
      ]
    }
  ],

  "metadata": {
    "source_blueprint": "floorplan_v1.png",
    "scale": 1.0
  }
}
```

### Schema Adaptation Layer (`SceneAdapter`)

If Member 1 outputs raw pixel dimensions, unit variations (`mm`, `cm`, `inches`, `feet`), nested walls (`wall["doors"] = [...]`), or an inverted image Y-axis, Member 2 provides `src.adapter.SceneAdapter` to automatically normalize the payload into the canonical `SceneSpecification`:

```bash
# Automatically normalize external/Member 1 variants on the fly
python -m src.cli validate input.json --use-adapter
python -m src.cli generate input.json -o output.glb --use-adapter
```

---

## Architectural Features

### 1. Volumetric Walls with True Openings
Walls are **not thin 2D planes**. They are generated as volumetric rectangular prisms in local coordinate space transformed to 3D world space.
- Openings (doors and windows) create **true physical voids**.
- Lintel blocks are automatically constructed above doors and windows.
- Sill blocks are constructed below windows.
- Multiple openings on the same wall are automatically sorted and partitioned into watertight solid segments.
- Optional architectural frames, door panels, and translucent window glass are generated as modular child nodes.

### 2. Multi-Room Floors and Ceilings
- Uses robust 2D polygon triangulation (via `mapbox-earcut` and `shapely`).
- Supports arbitrary polygon geometries (convex, concave, L-shaped, polygonal suites).
- Floors are generated at `z = 0.0m` (extending downwards as solid slabs).
- Ceilings are generated at `z = wall_height` (extending upwards as solid slabs).
- Partition walls shared between adjacent rooms are detected (`detect_shared_walls`), preventing redundant co-located walls.

### 3. Hierarchical Scene Graph
Preserves complete provenance for every 3D mesh:
- Source 2D coordinates (`start`, `end`, `polygon`)
- Real-world 3D dimensions (`length_m`, `thickness_m`, `height_m`, `area_m2`, `perimeter_m`)
- Spatial relationships (e.g. wall borders `["Living Room", "Bedroom"]`, opening attached to `wall_01`)
- 3D Bounding Box in meters

### 4. Robust Validation & Accuracy Report
Before generating 3D meshes, input is strictly verified:
- Rejects malformed JSON, NaN, Infinity, negative dimensions, and zero-length walls.
- Verifies door and window references exist.
- Verifies door/window offsets and spans do not exceed wall length.
- Detects overlapping openings on the same wall.
- Validates room polygon topology (no self-intersections, minimum area).
- Generates a detailed accuracy report calculating room floor areas, perimeters, wall lengths, and total square meters.

---

## Installation & Setup

Ensure Python 3.10+ is installed:

```powershell
# 1. Create and activate virtual environment
python -m venv .venv
.\.venv\Scripts\Activate.ps1

# 2. Install dependencies
pip install -r requirements.txt
```

---

## CLI Usage

Member 2 provides an intuitive CLI via `python -m src.cli`:

### 1. Validate a Scene
```powershell
python -m src.cli validate examples/sample_scene.json
```
Output:
```
[VALIDATION SUCCESS] sample_scene.json is a valid architectural scene!
  Rooms:   4/4
  Walls:   8/8
  Doors:   4/4
  Windows: 4/4
  Total Floor Area: 48.00 m²
```

### 2. Generate Accuracy & Dimension Report
```powershell
python -m src.cli report examples/sample_scene.json
```

### 3. Generate and Export 3D Model
```powershell
# Export to GLB (default)
python -m src.cli generate examples/sample_scene.json -o output.glb -f glb

# Export to OBJ
python -m src.cli generate examples/sample_scene.json -o output.obj -f obj

# Export to PLY
python -m src.cli generate examples/sample_scene.json -o output.ply -f ply
```

### 4. Launch Interactive 3D Viewer
```powershell
python -m src.cli view examples/sample_scene.json --port 8080
```
This automatically starts the local HTTP server and opens your browser.

---

## 3D Viewer & Visual Debug Inspector

The viewer is accessible at `http://localhost:8080/`:

1. **Navigation Controls**:
   - **Left Click + Drag**: Orbit / Rotate around the room
   - **Right Click + Drag**: Pan horizontally and vertically
   - **Scroll Wheel**: Smooth zoom in / out
   - **Preset Buttons**: "3D Orbit", "Top (2D Plan)", "Reset Camera"

2. **Visibility Layer Toggles**:
   - `Walls`: Toggle wall geometry
   - `Doors`: Toggle door frames and panels
   - `Windows`: Toggle window frames and translucent glazing
   - `Floors`: Toggle floor slabs
   - `Ceilings`: Unchecked by default to provide an immediate unobstructed interior view
   - `Wireframe`: Toggle wireframe overlay across all architectural materials
   - `Grid & Axes`: Toggle 1-meter CAD ground grid and RGB axis indicator

3. **Visual Debug Inspector (Raycasting)**:
   - Click directly on any wall, floor, door, or window in the scene.
   - The selected mesh highlights with an amber glow.
   - The right-side HUD updates instantly displaying:
     - **Entity Name & ID**
     - **Exact Dimensions** (Length, Thickness, Height, Area, Perimeter)
     - **Source 2D Coordinates**
     - **Connected Entities** (Bordering rooms, attached doors/windows)

---

## Running Automated Tests

Run the complete test suite with `pytest`:

```powershell
.\.venv\Scripts\pytest.exe -v
```

All 12 test suites cover:
- **TEST 1**: Single rectangular room (4 walls, 1 floor, 1 ceiling)
- **TEST 2**: Room with one door (verifies opening void, lintel geometry, door frame/leaf)
- **TEST 3**: Room with one window (verifies opening void, sill geometry, lintel geometry, frame/glass)
- **TEST 4**: Room with door and window on the same wall
- **TEST 5**: Multiple connected rooms
- **TEST 6**: Shared partition wall detection between rooms
- **TEST 7**: Arbitrary wall orientations (0°, 90°, 45°, diagonal)
- **TEST 8**: Non-square / L-shaped room polygon triangulation
- **TEST 9**: Malformed / invalid scene rejection (missing walls, out-of-bounds openings, overlaps)
- **TEST 10**: Exact dimension preservation within numerical tolerance ($10^{-4}$m)
- **TEST 11**: Export file integrity (GLB, OBJ, PLY)
- **TEST 12**: Security and untrusted input checks (rejection of NaN, Infinity, unbounded coordinates)

---

## Project Structure

```
├── examples/
│   └── sample_scene.json       # Synthetic 4-room apartment test fixture
├── schemas/
│   └── scene.schema.json       # JSON Schema contract for Member 1
├── src/
│   ├── geometry/
│   │   ├── materials.py        # Neutral architectural PBR materials
│   │   ├── room_builder.py     # Floor & ceiling triangulation and shared wall analysis
│   │   └── wall_builder.py     # Volumetric walls with true physical openings
│   ├── viewer/
│   │   ├── server.py           # Local HTTP server with API endpoints
│   │   └── static/             # Three.js 3D viewer & debug inspector
│   │       ├── index.html
│   │       ├── style.css
│   │       └── viewer.js
│   ├── adapter.py              # Member 1 normalization & unit conversion
│   ├── cli.py                  # Command-line interface
│   ├── exporter.py             # GLB, GLTF, OBJ, PLY export
│   ├── scene_graph.py          # Structured hierarchical scene graph
│   ├── schema.py               # Pydantic data models & coordinate conventions
│   └── validator.py            # Geometric & relational validation and accuracy report
├── tests/
│   └── test_geometry.py        # Automated test suite
├── pyproject.toml              # Build & package configuration
├── requirements.txt            # Python dependencies
└── README_MEMBER2.md           # Documentation
```
