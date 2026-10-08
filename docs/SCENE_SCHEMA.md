# Member 2 → Member 3 Scene Specification Contract
`validated_scene.json` Documentation

## Overview
This document specifies the exact JSON schema produced by **Member 2 (Geometry & Topology Processing)** and consumed directly by **Member 3 (3D Model Generation & Three.js Viewer)**.

Member 3 receives geometrically validated, topologically clean scene data where wall collinear fragments have been unified, corner gaps snapped, openings associated with continuous host walls, and room boundaries mathematically verified. Member 3 does **not** need to perform any geometry cleanup, heuristics, or image-space guessing.

---

## 1. Top-Level Specification

```json
{
  "version": "1.0",
  "units": "pixels" | "meters",
  "coordinate_system": "image" | "world",
  "image": {
    "width": 512,
    "height": 260
  },
  "scale": {
    "meters_per_pixel": null | float,
    "source": "unknown" | "explicit" | "reference_measurement",
    "confidence": 0.0 | float,
    "metric_available": false | true
  },
  "defaults": {
    "wall_height": 3.0,
    "door_height": 2.1,
    "window_sill_height": 0.9,
    "window_height": 1.2
  },
  "walls": [ ... ],
  "removed_walls": [ ... ],
  "wall_reassignments": { ... },
  "doors": [ ... ],
  "windows": [ ... ],
  "rooms": [ ... ],
  "topology_operations": [ ... ],
  "validation": { ... }
}
```

### Units and Coordinate System
- **`units`**: 
  - `"pixels"` (default when scale is unknown; prevents fabricating physical measurements).
  - `"meters"` (when authenticated physical scale was supplied or calibrated).
- **`coordinate_system`**:
  - `"image"`: $X \in [0, \text{width}]$ (left to right), $Y \in [0, \text{height}]$ (top to bottom).
  - `"world"`: standard metric Cartesian coordinate system with $Z$ as upward normal.
- **`defaults`**: Architectural fallback dimensions (in meters) for vertical 3D extrusion when height properties are omitted from individual elements.

---

## 2. Walls (`walls[]`)

Each wall represents an active continuous architectural wall segment.

```json
{
  "id": "w1",
  "source": {
    "start": [238.0, 18.0],
    "end": [79.5, 19.0],
    "thickness": 16.0
  },
  "source_ids": ["w1", "w4", "w3"],
  "corrected": true,
  "correction_reason": "merged_collinear_fragments",
  "geometry": {
    "start": [79.5, 19.0],
    "end": [503.0, 18.0],
    "thickness": 15.97,
    "length": 423.5
  },
  "start": [79.5, 19.0],
  "end": [503.0, 18.0],
  "thickness": 15.97
}
```

### Fields
| Field | Type | Description |
| :--- | :--- | :--- |
| `id` | `string` | Unique identifier of the wall. |
| `start` / `geometry.start` | `[float, float]` | 2D start point $[X, Y]$ in canvas units. |
| `end` / `geometry.end` | `[float, float]` | 2D end point $[X, Y]$ in canvas units. Vector direction defines $U$-axis for openings. |
| `thickness` / `geometry.thickness` | `float` | Wall thickness perpendicular to the wall axis. |
| `geometry.length` | `float` | Euclidean length of the wall from `start` to `end`. |
| `source` | `object` | Unaltered Member 1 input data preserved for provenance. |
| `source_ids` | `list[string]` | List of original Member 1 wall IDs unified into this host wall. |
| `corrected` | `boolean` | `true` if snapped, merged, or adjusted during topology cleanup. |
| `correction_reason` | `string \| null` | Description of the topology operation applied. |

---

## 3. Retired Artifact Walls (`removed_walls[]`)

Walls identified as extraction artifacts (e.g. non-structural line stubs inside door/window opening gaps) are retired here rather than silently deleted:

```json
{
  "id": "w9",
  "source": { "start": [72.0, 150.0], "end": [84.0, 150.0], "thickness": 4.0 },
  "geometry": { "start": [72.0, 150.0], "end": [84.0, 150.0], "thickness": 4.0, "length": 12.0 },
  "corrected": true,
  "correction_reason": "extraction_artifact_in_opening_gap"
}
```

---

## 4. Doors (`doors[]`) and Windows (`windows[]`)

Openings are mathematically bound to their continuous host walls with explicit interval bounds.

```json
{
  "id": "d3",
  "type": "door",
  "wall_id": "w2",
  "source_wall_id": "w11",
  "corrected": true,
  "correction_reason": "host_wall_reassigned_after_topology_cleanup",
  "offset": 171.0,
  "width": 30.0,
  "height": 2.1,
  "opening_start": 156.0,
  "opening_end": 186.0,
  "geometry": {
    "center": [79.91, 190.0],
    "start": [79.84, 175.0],
    "end": [79.99, 205.0],
    "opening_start": 156.0,
    "opening_end": 186.0,
    "fits_within_wall": true
  },
  "position": 0.855
}
```

### Canonical vs. Backward-Compatible Fields
- **`offset` (Canonical)**:
  - Distance (in units) measured along the host wall from `geometry.start` to the opening center.
  - Formula: $\text{opening\_center} = \text{wall.start} + \text{offset} \cdot \hat{u}$.
- **`opening_start` & `opening_end`**:
  - Interval $[\text{offset} - \frac{\text{width}}{2}, \text{offset} + \frac{\text{width}}{2}]$ along the host wall.
  - Guarantees $0 \le \text{opening\_start} < \text{opening\_end} \le \text{wall.length}$.
- **`position` (Backward-Compatible)**:
  - Normalized ratio in $[0.0, 1.0]$: $\text{position} = \frac{\text{offset}}{\text{wall.length}}$.
- **`sill_height`** (Windows only):
  - Height above finished floor (default: 0.9m).

---

## 5. Rooms (`rooms[]`)

Room polygons define interior floor boundaries and room labels.

```json
{
  "id": "room_1",
  "label": "Master Bedroom",
  "polygon": [[79.5, 19.0], [311.9, 18.45], [317.5, 145.04], [78.0, 145.0]],
  "geometry": {
    "polygon": [[79.5, 19.0], [311.9, 18.45], [317.5, 145.04], [78.0, 145.0]],
    "area": 29624.5,
    "perimeter": 732.1,
    "bounds": [78.0, 18.45, 317.5, 145.04],
    "centroid": [198.2, 81.7],
    "num_vertices": 4
  }
}
```

---

## 6. Validation Report Contract (`validation_report.json`)

The validation report accompanies the scene handoff with 3-tier severity:

```json
{
  "status": "PASS",
  "valid": true,
  "errors": [],
  "warnings": [
    {
      "type": "boundary_door_position",
      "element_type": "door",
      "element_id": "d1",
      "severity": "WARNING",
      "message": "Door 'd1' is positioned at the extreme wall boundary"
    }
  ],
  "info": [],
  "summary": {
    "status": "PASS",
    "wall_count": 8,
    "door_count": 4,
    "window_count": 4,
    "room_count": 3,
    "error_count": 0,
    "warning_count": 2,
    "info_count": 0,
    "topology_snaps": 13
  }
}
```

### Severity Tiers
- **`ERROR`**: Blocking invalidity (missing wall reference, opening outside wall, zero-length wall, invalid polygon). Scene `status` = `"FAIL"`.
- **`WARNING`**: Non-blocking architectural notice (opening touching corner/boundary, unusual thickness, short wall). Scene `status` = `"PASS"`.
- **`INFO`**: Audit log of topology corrections (endpoint snapped, wall merged, artifact retired).
