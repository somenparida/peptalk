# HNX26EPS06: 3D Scene Generation from Blueprints
**HackNex 2026 Problem Statement 06 (Mode A: Floor Plan → 3D Model)**

A production-ready, modular, unified computer vision and procedural 3D graphics pipeline built in Python and Three.js. Automatically transforms 2D architectural blueprints and CAD floor plans (PNG, JPG, JSON) into watertight, dimension-preserving, semantically structured 3D scenes in `.glb` format with an interactive local Three.js web viewer.

---

## Architecture & Unified Pipeline

```
  Architectural Blueprint / CAD Spec (PNG, JPG, JSON)
                            ↓
  Stage 1: Floor Plan Parser & 2D Vector Extractor (`src/parser/`)
    - Computer vision vectorization (adaptive thresholding, morphological separation, Hough transform)
    - Automatic scale bar metric calibration & benchmark dataset generator
                            ↓
  Stage 2: Topological Graph & Geometry Cleanup Engine (`src/geometry/`)
    - Topological junction graph (L, T, X intersections)
    - Corner and T-junction snapping
    - Collinear wall merging across door/window gaps
    - 1D parametric opening interval binding [start, end] on host walls
    - Enclosed room polygon topology & area calculation ($m^2$)
    - 3-Tier Validation System (ERROR, WARNING, INFO)
                            ↓
  Stage 3: Procedural 3D Mesh Reconstruction Engine (`src/builder/`)
    - Watertight wall solids with exact rectangular cutouts
    - Lintel geometry above doors & windows
    - Protruding architectural window sills
    - 3D door frames and wood door leaves
    - 3D window frames and transparent glass panes
    - Extruded room floor slabs, ceiling slabs, and foundation plinth
                            ↓
  Stage 4: GLB Exporter & Interactive Web 3D Viewer (`src/exporter/`, `src/viewer/`)
    - Binary `.glb` exporter with companion metadata JSON
    - Self-contained Three.js viewer with Orbit & 1st-Person Walkthrough modes
    - Real-time 3D dimension measurement ruler
    - Component layer toggles (ceilings, cutaway dollhouse, wireframe, X-ray)
    - Scene inspector sidebar with room areas ($m^2$) and wall metrics
```

---

## Directory Structure

```
d:\ai wala civil engineer\
├── main.py                    # Master CLI entrypoint (process, view, test, benchmark)
├── requirements.txt           # Pinned virtual environment dependencies
├── pytest.ini                 # Pytest test configuration
├── src/
│   ├── config.py              # Architectural dimensions & geometric defaults
│   ├── models.py              # Core dataclasses (Point2D, WallEdge, RoomPolygon, etc.)
│   ├── parser/
│   │   ├── pipeline.py            # Unified format auto-detection router
│   │   ├── image_detector.py      # Computer vision vectorizer & scale detector
│   │   ├── structured_parser.py   # Structured JSON/CAD specification parser
│   │   └── synthetic_generator.py # Ground-truth benchmark floor plan generator
│   ├── geometry/
│   │   ├── graph.py           # Topological wall graph and junction analysis
│   │   ├── snapping.py        # L-junction & T-junction snapping engine
│   │   ├── merging.py         # Collinear wall segment merging
│   │   ├── binding.py         # 1D parametric opening interval binder
│   │   ├── rooms.py           # Room polygon topology & area calculation
│   │   └── validator.py       # 3-Tier validation engine (ERROR, WARN, INFO)
│   ├── builder/
│   │   ├── mesh_utils.py      # Watertight prism and polygon triangulation primitives
│   │   ├── wall_builder.py    # Wall solids with apertures and lintels
│   │   ├── opening_builder.py # Door frames, leaves, window frames, glass, sills
│   │   ├── slab_builder.py    # Extruded floor slabs, ceiling slabs, plinth
│   │   └── scene_builder.py   # Assembles semantic architectural scene
│   ├── exporter/
│   │   └── glb_exporter.py    # Binary GLB and metadata JSON exporter
│   └── viewer/
│       ├── server.py          # Local HTTP streaming server
│       └── web/
│           └── index.html     # Interactive Three.js 3D application
├── tests/
│   ├── test_geometry.py       # Snapping, merging, binding, validation tests
│   ├── test_parser.py         # Image and structured parser tests
│   ├── test_builder.py        # Watertight procedural mesh tests
│   ├── test_exporter.py       # GLB export integrity tests
│   ├── test_viewer.py         # Web viewer server tests
│   └── test_e2e.py            # End-to-end integration tests
└── data/benchmark/            # Clean benchmark datasets
```

---

## Architectural Dimension Standards (SI Metric)

| Component | Default Dimension | Description |
| :--- | :--- | :--- |
| **Wall Height** | `2.80 m` | Standard residential floor-to-ceiling clearance |
| **Wall Thickness** | `0.20 m - 0.25 m` | Structural masonry / concrete wall thickness |
| **Door Aperture** | `2.10 m (H) × 0.90 m (W)` | Standard entrance and room passage opening |
| **Window Aperture** | `1.20 m (H) × 1.20 m (W)` | Architectural daylight aperture |
| **Window Sill** | `0.90 m` | Elevation from finished floor to bottom of window |
| **Floor Slab** | `0.15 m` | Reinforced concrete structural floor depth |
| **Ceiling Slab** | `0.12 m` | Reinforced ceiling / roof deck slab |

---

## Quickstart & CLI Commands

All commands run using the local Python virtual environment (`.\.venv\Scripts\python.exe`):

### 1. Generate Ground-Truth Benchmark Dataset
```powershell
.\.venv\Scripts\python.exe main.py benchmark --outdir data/benchmark
```
Generates both:
- `data/benchmark/benchmark_floorplan.png` (high-res blueprint with doors, windows, scale bar)
- `data/benchmark/benchmark_ground_truth.json` (exact metric coordinates)

### 2. Process a Blueprint / Floor Plan to 3D GLB
```powershell
# From structured JSON specification
.\.venv\Scripts\python.exe main.py process data/benchmark/benchmark_ground_truth.json --outdir output

# From raster blueprint image (PNG, JPG) with automatic scale detection
.\.venv\Scripts\python.exe main.py process data/benchmark/benchmark_floorplan.png --outdir output

# Process and immediately launch 3D Web Viewer
.\.venv\Scripts\python.exe main.py process data/benchmark/benchmark_ground_truth.json --view
```

### 3. Launch Interactive 3D Web Viewer
```powershell
.\.venv\Scripts\python.exe main.py view --glb output/benchmark_ground_truth_scene.glb --port 8080
```
Open [http://localhost:8080](http://localhost:8080) in any web browser.

### 4. Run Automated Test Suite
```powershell
.\.venv\Scripts\python.exe main.py test
# or directly via pytest:
.\.venv\Scripts\pytest.exe -v
```

---

## 3D Web Viewer Features

- **Dual Camera Navigation**:
  - `Orbit Mode`: Smooth 3rd-person rotation, pan, zoom, and framing.
  - `Walkthrough Mode`: First-person FPS controls (`W`, `A`, `S`, `D` + Mouse Look) at true eye level (`1.6m`).
- **Interactive 3D Ruler**: Click any two points in the scene to measure point-to-point distances ($m$), along with Cartesian deltas ($\Delta X, \Delta Y, \Delta Z$).
- **Architectural Layer Toggles**:
  - Ceilings On/Off
  - Roof Cutaway (Dollhouse view)
  - Wireframe Overlay
  - Wall X-Ray Transparency
- **Scene Inspector Sidebar**: Displays total floor area ($m^2$), wall perimeter ($m$), opening counts, and an interactive room explorer that auto-focuses the camera on clicked rooms.
