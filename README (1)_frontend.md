# Floor-Plan to 3D Scene Reconstruction

## Overview

This project implements a browser-based architectural scene reconstruction pipeline that converts structured floor-plan scene data into an interactive Three.js 3D/2D representation.

The implemented workflow takes room, wall, door, and window information from a JSON scene description, validates the data, converts the floor-plan coordinate system into Three.js coordinates, procedurally generates architectural geometry, displays measurements and room information, provides 2D/3D viewing controls, and exports the reconstructed scene as a GLB asset.

The current implementation was integrated and validated using Member 2's scene data.

### Current integration result

**Status: PASS — READY FOR TEAM INTEGRATION**

The validated Member 2 scene contains:

- 4 rooms
- 8 walls
- 4 doors
- 4 windows
- 2.8 m wall height
- Metric units
- 8.0 m × 6.0 m nominal floor-plan dimensions

Automated validation completed with:

- **103 tests run**
- **103 tests passed**
- **0 tests failed**
- Production build passed
- Browser console clean
- 3D and 2D visual QA passed
- GLB export and reload passed

---

# 1. Project Goal

The goal of this part of the system is to reconstruct an architectural scene from structured floor-plan data.

The pipeline can be summarized as:

```text
Structured Scene JSON
        ↓
Schema Validation
        ↓
Coordinate / Dimension Adaptation
        ↓
Procedural Geometry Generation
        ↓
Walls + Floors + Doors + Windows
        ↓
Room Labels + Areas + Dimensions
        ↓
Interactive 3D / 2D Viewer
        ↓
Validation & QA
        ↓
GLB Export
        ↓
Downstream AR/VR / Asset Pipeline
```

The system is designed so that floor-plan information supplied by an upstream component can be converted into a consistent Three.js scene without manually modelling each architectural element.

---

# 2. Main Technologies

## Frontend / Rendering

- JavaScript
- Three.js
- Vite
- HTML
- CSS

## Geometry and 3D

- Three.js procedural geometry
- `THREE.Shape`
- `THREE.ExtrudeGeometry`
- `THREE.BufferGeometry`
- Three.js line geometry
- GLTF/GLB export and loading

## Validation and Testing

- Node.js
- npm
- Automated JavaScript tests
- Browser-based QA
- Headless Microsoft Edge
- Playwright-related browser tooling

## Export

- Three.js `GLTFExporter`
- GLB binary output

---

# 3. Project Structure

The relevant project structure is:

```text
peptalk/
│
├── index.html
├── package.json
│
├── src/
│   ├── main.js
│   │
│   ├── data/
│   │   └── SceneValidator.js
│   │
│   ├── scene/
│   │   ├── WallGenerator.js
│   │   ├── DoorGenerator.js
│   │   ├── WindowGenerator.js
│   │   ├── FloorGenerator.js
│   │   ├── RoomGenerator.js
│   │   ├── DimensionRenderer.js
│   │   └── Labels.js
│   │
│   ├── export/
│   │   └── GLBExporter.js
│   │
│   └── viewer/
│       └── ViewerControls.js
│
├── tests/
│   ├── verify_all.js
│   └── test_reconstruction.js
│
├── data/
│   ├── sample_scene.json
│   └── scene.json
│
├── scene/
├── export/
└── viewer/
```

The project also produced a validated GLB output:

```text
reconstructed_scene.glb
```

---

# 4. Scene Data Input

The reconstruction system works with structured JSON rather than directly modelling a floor plan by hand.

The scene data describes architectural entities such as:

- Rooms
- Walls
- Doors
- Windows
- Wall height
- Units
- Geometric coordinates
- Dimensions
- Offsets
- Sill heights

A representative scene contains:

```text
Rooms  → 4
Walls  → 8
Doors  → 4
Windows → 4
Wall height → 2.8 m
Units → meters
```

The implementation also supports compatibility between the newer Member 2 schema and the legacy schema.

---

# 5. Schema Adaptation

One of the major integration tasks was adapting Member 2's scene representation to the existing Three.js reconstruction system.

## 5.1 Wall Height

The implementation supports both:

```text
root-level:
wall_height
```

and the legacy:

```text
settings.wallHeight
```

Priority is given to the root-level `wall_height`.

If neither value is available, the system falls back to:

```text
3.0 m
```

This compatibility handling was implemented across:

- `SceneValidator.js`
- `WallGenerator.js`
- `DoorGenerator.js`
- `WindowGenerator.js`

---

# 6. Coordinate System Conversion

The floor-plan input uses a 2D coordinate representation where the second coordinate represents the horizontal floor-plan depth.

Three.js uses:

```text
X = horizontal
Y = vertical
Z = horizontal depth
```

Therefore, the project converts floor-plan coordinates:

```text
[x, y]
```

into Three.js coordinates:

```text
[x, height, y]
```

Conceptually:

```text
Floor-plan:

        y
        ↑
        |
        |
        +--------→ x


Three.js:

             Y
             ↑
             |
             |
             +--------→ X
            /
           /
          Z
```

The conversion is applied consistently to:

- Walls
- Floors
- Doors
- Windows
- Room labels
- Dimension lines
- Bounding boxes
- Camera framing
- GLB export

This consistency is important because a coordinate conversion bug in one subsystem would cause elements to appear misaligned in the final scene.

---

# 7. Wall Generation

Walls are generated procedurally from their start/end coordinates.

The validated scene contains eight walls:

| Wall | Expected Length | Actual Length |
|---|---:|---:|
| `wall_south` | 8.0 m | 8.0 m |
| `wall_north` | 8.0 m | 8.0 m |
| `wall_west` | 6.0 m | 6.0 m |
| `wall_east` | 6.0 m | 6.0 m |
| `wall_partition_living_bed` | 4.8 m | 4.8 m |
| `wall_partition_kit_bath` | 3.2 m | 3.2 m |
| `wall_partition_living_kit` | 3.5 m | 3.5 m |
| `wall_partition_bed_bath` | 2.5 m | 2.5 m |

### Wall thickness

The current implementation uses:

- Perimeter walls: **0.20 m**
- Interior partition walls: **0.15 m**

The wall connections were visually validated and connect cleanly along their centerlines.

---

# 8. Door Generation

Doors are attached to their corresponding walls using a metric offset.

The wall direction is calculated as:

```text
direction = (end - start) / ||end - start||
```

The door center is then calculated using:

```text
door_center = start + direction × offset
```

This means that the door position is based on an actual metric distance along the wall instead of an arbitrary screen coordinate.

## Door properties

Explicit door values from the scene are respected, including:

- Width
- Height
- Wall association
- Offset

Door height in the validated scene:

```text
2.10 m
```

Door bottoms are placed flush with the floor.

The implementation also retains support for the legacy normalized:

```text
door.position
```

value as a fallback.

## Validated doors

| Door | Wall | Offset | Width | Height |
|---|---|---:|---:|---:|
| `door_entrance` | `wall_south` | 1.5 m | 0.90 m | 2.10 m |
| `door_bedroom` | `wall_partition_living_bed` | 1.8 m | 0.85 m | 2.10 m |
| `door_kitchen` | `wall_partition_living_kit` | 1.2 m | 0.90 m | 2.10 m |
| `door_bathroom` | `wall_partition_kit_bath` | 1.0 m | 0.80 m | 2.10 m |

All four doors passed validation.

---

# 9. Window Generation

Windows use the same metric offset principle as doors.

The window center is calculated along the corresponding wall direction.

The system respects:

- Width
- Height
- Wall
- Offset
- Sill height

The vertical position is calculated as:

```text
Y = sill_height + height / 2
```

This ensures that the lower edge of the window is positioned at the specified sill height.

## Validated windows

| Window | Wall | Offset | Width | Height | Sill |
|---|---|---:|---:|---:|---:|
| `window_living` | `wall_west` | 1.0 m | 1.60 m | 1.40 m | 0.90 m |
| `window_bedroom` | `wall_north` | 1.5 m | 1.50 m | 1.20 m | 1.00 m |
| `window_kitchen` | `wall_east` | 1.2 m | 1.20 m | 1.10 m | 1.10 m |
| `window_bathroom` | `wall_north` | 6.0 m | 0.80 m | 0.80 m | 1.40 m |

All four windows passed validation.

---

# 10. Room / Floor Generation

Rooms are represented as 2D polygons.

The system preserves arbitrary room polygons rather than assuming that every room must be represented by a fixed rectangle.

Room geometry is generated using:

```text
THREE.Shape
        ↓
THREE.ExtrudeGeometry
```

Room boundaries are also represented as closed line loops.

## Room area calculation

The project uses the polygon area calculation based on the Shoelace formula.

Conceptually:

```text
Area =
1/2 × |Σ(xᵢyᵢ₊₁ - xᵢ₊₁yᵢ)|
```

## Room centroid calculation

Room centroids are calculated using a polygon-based centroid method based on Green's theorem.

Room names are displayed using the calculated room positions.

## Validated rooms

| Room | Vertices | Centroid | Area |
|---|---:|---|---:|
| Living Room | 4 | [2.40, 1.75] | 16.80 m² |
| Kitchen | 4 | [6.40, 1.75] | 11.20 m² |
| Bedroom | 4 | [2.40, 4.75] | 12.00 m² |
| Bathroom | 4 | [6.40, 4.75] | 8.00 m² |

All four room polygons passed validation.

---

# 11. Room Labels

The viewer displays room information directly inside the reconstructed scene.

Labels include:

- Room name
- Room area
- Room position

The labels are positioned using room centroids.

For example:

```text
Living Room
16.80 m²
```

This provides immediate spatial information without requiring the user to inspect the raw JSON.

---

# 12. Dimension Rendering

The system renders dimension information for the architectural geometry.

The validated scene contains dimension indicators for all eight walls.

The dimensions provide metric measurements corresponding to the source floor-plan data.

Validated dimensions include:

```text
8.0 m
8.0 m
6.0 m
6.0 m
4.8 m
3.2 m
3.5 m
2.5 m
```

The dimension rendering was visually verified successfully.

---

# 13. Camera and Scene Framing

The viewer automatically frames the reconstructed scene.

For the validated scene:

```text
Nominal layout:
8.0 m × 6.0 m
```

Including wall thickness, the overall bounding dimensions were:

```text
8.24 m × 6.23 m
```

The camera successfully frames the complete layout.

---

# 14. 2D and 3D Viewer

The project supports both:

## 3D mode

A perspective architectural view showing:

- Walls
- Floors
- Doors
- Windows
- Room labels
- Dimensions

## 2D mode

A top-down floor-plan representation.

The 2D mode was tested and aligned correctly with the underlying reconstructed geometry.

---

# 15. Visibility Controls

The viewer includes layer visibility controls.

The validation confirmed that all six visibility control chips respond correctly.

The controls allow individual scene categories/layers to be toggled without rebuilding the complete scene.

This is useful for:

- Inspecting walls separately
- Hiding dimensions
- Inspecting rooms
- Checking openings
- Comparing 2D/3D representations

---

# 16. Scene Validation

`SceneValidator.js` is responsible for checking and normalizing incoming scene data before geometry generation.

The validation layer was adapted to support the Member 2 scene schema while retaining legacy compatibility.

Validation covers important architectural properties including:

- Scene structure
- Wall information
- Wall height
- Door references
- Window references
- Room polygons
- Dimensions
- Coordinate data

This reduces the chance of malformed scene data reaching the geometry generation layer.

---

# 17. Main Scene Pipeline

The main runtime flow is handled through `main.js`.

The high-level process is:

```text
Load Scene JSON
       ↓
Validate Scene
       ↓
Resolve Compatible Schema
       ↓
Convert Coordinates
       ↓
Generate Walls
       ↓
Generate Floors / Rooms
       ↓
Generate Doors
       ↓
Generate Windows
       ↓
Calculate Areas / Centroids
       ↓
Render Labels
       ↓
Render Dimensions
       ↓
Frame Camera
       ↓
Enable Viewer Controls
       ↓
Display 2D / 3D Scene
```

---

# 18. GLB Export

The reconstructed Three.js scene can be exported to GLB.

The relevant implementation is:

```text
src/export/GLBExporter.js
```

The project also performed additional work to make GLB export reliable in the Node/browser-compatible testing environment.

The resulting file was:

```text
reconstructed_scene.glb
```

## Export validation

The generated GLB contained:

```text
File size: 107.4 KB
Architectural meshes: 60
```

The file was successfully reloaded using `GLTFLoader`.

---

# 19. GLB Geometry Validation

The exported scene was checked after reloading.

Validation confirmed:

### Export

```text
PASS
```

The GLB file was successfully written.

### Reload

```text
PASS
```

The exported file was parsed successfully.

### Dimensions

```text
8.24 m × 2.90 m × 6.23 m
```

The bounding box matched the expected reconstructed scene.

### Orientation

```text
PASS
```

The exported scene preserved:

- Right-handed coordinate orientation
- Y-up orientation
- 1.0 unit scale

---

# 20. Testing

Multiple validation levels were performed.

## 20.1 Automated test suite

Command:

```bash
npm test
```

Result:

```text
103 tests
103 passed
0 failed
```

This is the primary automated validation result.

---

## 20.2 Reconstruction test

The project also ran:

```bash
node test_reconstruction.js
```

This was used to verify reconstruction and export-related behavior.

---

## 20.3 Full verification

The project ran:

```bash
node tests/verify_all.js
```

The verification suite passed.

---

## 20.4 Production build

Command:

```bash
npm run build
```

Result:

```text
PASS
```

The Vite production bundle compiled successfully.

---

# 21. Browser QA

Browser-based validation was performed after starting the Vite development server.

The server was launched using:

```bash
npx vite --port 5173
```

The scene was then tested through a headless browser environment.

Browser QA checked:

- Scene rendering
- 3D view
- 2D view
- Walls
- Floors
- Doors
- Windows
- Labels
- Dimensions
- Camera framing
- Visibility controls
- Browser console

The browser console was clean:

```text
0 errors
0 unhandled rejections
```

---

# 22. Visual QA Results

The final visual validation produced the following results:

| Component | Result |
|---|---|
| Walls | PASS |
| Floors | PASS |
| Doors | PASS |
| Windows | PASS |
| Labels | PASS |
| Dimensions | PASS |
| Camera | PASS |
| 2D view | PASS |
| Visibility controls | PASS |

### Walls

All eight walls connect correctly with accurate corners and partitions.

### Floors

All four room floor polygons render correctly.

### Doors

All four doors are attached to their correct walls using metric offsets.

### Windows

All four windows are attached with correct elevations and sill heights.

### Labels

Room labels appear at calculated centroids and include room names and areas.

### Dimensions

All eight wall dimensions are rendered with metric indicators.

---

# 23. Overall Geometry

The validated architectural footprint is:

```text
Width  = 8.0 m
Depth  = 6.0 m
```

Including exterior wall thickness:

```text
Width  = 8.24 m
Depth  = 6.23 m
```

Wall height:

```text
2.8 m
```

The scene therefore represents a complete small architectural layout with four rooms.

---

# 24. Integration With Member 2

The current implementation represents the integration between Member 2's scene-generation output and the reconstruction/viewer component.

The integration report recorded:

```text
MEMBER 2 → MEMBER 3 INTEGRATION

Status:
PASS
```

The integration required adaptation of:

- Wall height schema
- Coordinate system
- Door offset representation
- Window offset representation
- Room polygon representation

After adaptation, all automated and visual checks passed.

The final integration status was:

```text
READY FOR TEAM INTEGRATION
```

---

# 25. Files Changed During Integration

The integration work modified the following files:

```text
src/data/SceneValidator.js
src/scene/WallGenerator.js
src/scene/DoorGenerator.js
src/scene/WindowGenerator.js
src/export/GLBExporter.js
src/main.js
index.html
tests/verify_all.js
```

The integration also produced:

```text
reconstructed_scene.glb
```

---

# 26. Important Implementation Details

## 26.1 Metric door positioning

Instead of assuming that a door's position is a normalized percentage along a wall, the system calculates its actual metric location.

```text
direction = normalized(end - start)

door_center = start + direction × offset
```

This allows a door to be specified directly using a physical distance.

---

## 26.2 Metric window positioning

Windows use the same principle:

```text
window_center = start + direction × offset
```

Vertical placement additionally uses:

```text
Y = sill_height + height / 2
```

---

## 26.3 Arbitrary room polygons

The reconstruction system does not rely exclusively on rectangular rooms.

The room polygon is converted directly into Three.js geometry, allowing more general floor-plan shapes.

---

## 26.4 Legacy compatibility

The implementation was deliberately made backward-compatible.

For example:

```text
wall_height
```

is preferred, while:

```text
settings.wallHeight
```

remains supported as a fallback.

Similarly, normalized legacy door positions are retained as a fallback where applicable.

---

# 27. Issues Found

## Critical issues

```text
None
```

## Important issues

```text
None
```

## Optional observations

### Interior wall thickness

Interior partition walls currently have:

```text
0.15 m
```

while perimeter walls have:

```text
0.20 m
```

The wall connections intersect cleanly along centerlines.

There is a small:

```text
0.025 m
```

overlap at T-junctions due to the use of extruded box meshes before CSG Boolean unioning.

This was classified as an expected optional observation rather than a blocking issue.

### Bathroom window

`window_bathroom` uses an offset of:

```text
6.0 m
```

along `wall_north`, which is an 8.0 m wall.

The resulting placement was verified as correct because it falls within the bathroom span.

---

# 28. Commands Used

## Install dependencies

```bash
npm install
```

## Run tests

```bash
npm test
```

## Run complete verification

```bash
node tests/verify_all.js
```

## Run reconstruction test

```bash
node test_reconstruction.js
```

## Build production bundle

```bash
npm run build
```

## Start development server

```bash
npx vite --port 5173
```

---

# 29. How to Run the Project

## Step 1 — Install dependencies

From the project root:

```bash
npm install
```

## Step 2 — Run automated tests

```bash
npm test
```

Expected result:

```text
103/103 tests passing
```

## Step 3 — Start the application

```bash
npx vite --port 5173
```

Open the local development URL provided by Vite.

## Step 4 — Load the scene

The application loads the structured scene data and reconstructs the architectural environment.

## Step 5 — Inspect the scene

Use the viewer to inspect:

- 3D reconstruction
- 2D floor plan
- Room labels
- Dimensions
- Architectural openings
- Layer visibility

## Step 6 — Export

Use the GLB export functionality to generate:

```text
reconstructed_scene.glb
```

---

# 30. Validation Checklist

The following checklist summarizes the completed work.

### Data

- [x] Scene JSON loaded
- [x] Scene schema validated
- [x] Member 2 schema integrated
- [x] Legacy compatibility maintained

### Geometry

- [x] Walls generated
- [x] Floors generated
- [x] Rooms generated
- [x] Doors generated
- [x] Windows generated
- [x] Room polygons preserved
- [x] Room areas calculated
- [x] Room centroids calculated

### Coordinate System

- [x] Floor-plan coordinates converted
- [x] Three.js Y-up coordinate system maintained
- [x] Coordinates applied consistently across scene components

### Visualization

- [x] 3D viewer
- [x] 2D viewer
- [x] Room labels
- [x] Dimension indicators
- [x] Camera auto-fit
- [x] Layer visibility controls

### Export

- [x] GLB export
- [x] GLB reload
- [x] Dimensions preserved
- [x] Orientation preserved
- [x] Scale preserved

### Testing

- [x] Automated tests
- [x] Reconstruction test
- [x] Browser QA
- [x] Visual QA
- [x] Production build
- [x] Console validation

---

# 31. Recommended Next Steps

The current system is validated and ready for team integration. The integration report identified the following possible next improvements.

## 31.1 Automated Member 2 → Member 3 data transfer

Current integration can be improved by adding:

```text
File-drop listener
        OR
API endpoint
```

This would allow Member 2's floor-plan outputs to be streamed directly into the reconstruction pipeline without manually transferring JSON files.

---

## 31.2 Area summary

Add an area breakdown card to the scene HUD.

For example:

```text
Total Floor Area
48.00 m²

Living Room
16.80 m²

Kitchen
11.20 m²

Bedroom
12.00 m²

Bathroom
8.00 m²
```

---

## 31.3 Unit toggle

Add a:

```text
Metric ↔ Imperial
```

toggle for dimensions and room areas.

---

## 31.4 AR/VR asset packaging

Package:

```text
reconstructed_scene.glb
```

into a downstream asset bundle for AR/VR walkthrough stages.

This allows the reconstructed scene to become an input asset for later visualization or immersive-viewing components.

---

# 32. Current Status

## Final Status

```text
READY FOR TEAM INTEGRATION
```

## Quality status

```text
Automated tests      : PASS
Build                : PASS
Browser QA           : PASS
Visual QA            : PASS
GLB export           : PASS
GLB reload           : PASS
Console errors       : 0
Critical issues      : 0
Important issues     : 0
```

## Final validation

```text
103 / 103 tests passed
```

The reconstructed scene successfully represents:

```text
4 Rooms
8 Walls
4 Doors
4 Windows
2.8 m Wall Height
8.0 m × 6.0 m Floor Plan
```

The resulting GLB was successfully generated and reloaded.

---

# 33. Integration Summary

The completed work establishes a complete pipeline from structured floor-plan data to an interactive, validated 3D architectural scene:

```text
Member 2 Scene Output
        │
        ▼
Scene Validation
        │
        ▼
Schema Adaptation
        │
        ▼
Coordinate Conversion
        │
        ▼
Procedural Reconstruction
        │
        ├── Walls
        ├── Floors
        ├── Rooms
        ├── Doors
        └── Windows
        │
        ▼
Visualization
        │
        ├── 3D View
        ├── 2D View
        ├── Labels
        ├── Dimensions
        └── Visibility Controls
        │
        ▼
Automated + Browser Validation
        │
        ▼
GLB Export
        │
        ▼
Downstream AR/VR Integration
```

The current implementation has passed the complete validation process and is ready to be consumed by the next stage of the team workflow.
