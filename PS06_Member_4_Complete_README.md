# HNX26EPS06 — Member 4 Complete Execution README

## Role: Integration + Scale + Evaluation + Release Manager

**Problem Statement:** HNX26EPS06 — 3D Scene Generation from Blueprints and Room Video  
**Chosen Mode:** Mode A — Floor Plan → 3D Model  
**Team Size:** 4  
**Time Limit:** 24 hours  
**Your role:** Member 4

---

# 1. Your Mission

You are the **integration owner**.

Your job is to make sure the work of:

- Member 1 — AI / segmentation
- Member 2 — geometry / computer vision
- Member 3 — 3D reconstruction / viewer

becomes **one working product**.

You are responsible for:

1. Creating the common pipeline.
2. Defining and protecting the data contract between members.
3. Creating the backend/API or CLI entry point.
4. Handling metric scale and dimension information.
5. Maintaining the test dataset.
6. Creating the baseline.
7. Running the held-out evaluation.
8. Measuring improvement from our proposed method.
9. Integrating all branches.
10. Stabilizing the final demo.
11. Preparing the technical evidence for judging.
12. Making sure the repository can be run by another person.

---

# 2. What the Official Problem Requires

For Mode A, the minimum bar is:

> Floor plan → 3D model with correctly placed walls, doors, windows and room dimensions.

The output must open in a real 3D viewer.

The Mode A judging criteria are:

| Criterion | Weight |
|---|---:|
| Layout accuracy vs. baseline | 40% |
| Completeness | 15% |
| Model quality | 15% |
| Usability in 3D viewer | 10% |
| Research contribution | 20% |
| **Total** | **100%** |

Therefore, your evaluation and integration work must focus on:

**accuracy → completeness → geometry quality → viewer usability → research evidence.**

---

# 3. Your Position in the Architecture

You sit between every member.

```text
                    INPUT
                      │
                      ▼
             ┌─────────────────┐
             │  Member 4       │
             │  API / Pipeline  │
             └────────┬────────┘
                      │
                      ▼
             ┌─────────────────┐
             │    Member 1     │
             │ AI Segmentation │
             └────────┬────────┘
                      │
                  masks
                      │
                      ▼
             ┌─────────────────┐
             │    Member 2     │
             │ Geometry Engine │
             └────────┬────────┘
                      │
                 scene.json
                      │
                      ▼
             ┌─────────────────┐
             │    Member 3     │
             │ 3D + GLB + UI  │
             └────────┬────────┘
                      │
                   scene.glb
                      │
                      ▼
             ┌─────────────────┐
             │    Member 4     │
             │ Evaluation/Test │
             └─────────────────┘
```

---

# 4. Your Golden Rule

## Never wait for another member.

If Member 1 has not finished:

Use a sample mask.

If Member 2 has not finished:

Use manually created `scene.json`.

If Member 3 has not finished:

Test with a dummy `.glb`.

Your work must progress independently.

---

# 5. Your Directory

You own these folders:

```text
integration/
evaluation/
data/
scripts/
docs/
```

Recommended structure:

```text
hacknex-ps06/
│
├── ai/
│
├── geometry/
│
├── reconstruction/
│
├── viewer/
│
├── integration/
│   ├── pipeline.py
│   ├── api.py
│   ├── schemas.py
│   ├── config.py
│   └── validators.py
│
├── evaluation/
│   ├── baseline.py
│   ├── metrics.py
│   ├── evaluate.py
│   ├── compare.py
│   └── results/
│
├── data/
│   ├── input/
│   ├── development/
│   ├── heldout/
│   ├── masks/
│   ├── expected/
│   └── demo/
│
├── scripts/
│   ├── run_pipeline.py
│   ├── validate_scene.py
│   └── evaluate_all.py
│
├── docs/
│   ├── evaluation.md
│   ├── architecture.md
│   └── demo.md
│
└── README.md
```

---

# 6. STEP 1 — Create the Common Contract

This is your most important early task.

Members 1, 2 and 3 must not communicate using random Python objects.

Define a stable file format.

We will use JSON.

---

# 7. `scene.json`

Create:

```text
scene_schema.json
```

Basic structure:

```json
{
  "version": "1.0",
  "units": "meters",

  "source": {
    "filename": "floorplan_01.png"
  },

  "scale": {
    "value": 0.01,
    "unit": "meters_per_pixel",
    "source": "estimated",
    "confidence": 0.75
  },

  "walls": [],
  "doors": [],
  "windows": [],
  "rooms": []
}
```

---

# 8. Wall Schema

Example:

```json
{
  "id": "wall_001",

  "start": [0.0, 0.0],

  "end": [5.0, 0.0],

  "thickness": 0.20,

  "height": 3.0,

  "source": "detected",

  "confidence": 0.94
}
```

### Required fields

```text
id
start
end
thickness
height
source
confidence
```

---

# 9. Door Schema

```json
{
  "id": "door_001",

  "wall_id": "wall_004",

  "position": 0.45,

  "width": 0.90,

  "height": 2.10,

  "source": "detected",

  "confidence": 0.88
}
```

`position` represents the normalized location along the wall:

```text
0.0 -------------------------- 1.0
START                          END
```

---

# 10. Window Schema

```json
{
  "id": "window_001",

  "wall_id": "wall_002",

  "position": 0.65,

  "width": 1.20,

  "sill_height": 0.90,

  "height": 1.20,

  "source": "detected",

  "confidence": 0.91
}
```

---

# 11. Room Schema

```json
{
  "id": "room_001",

  "label": "bedroom",

  "polygon": [
    [0.0, 0.0],
    [4.0, 0.0],
    [4.0, 3.5],
    [0.0, 3.5]
  ],

  "source": "inferred",

  "confidence": 0.82
}
```

Room labels are optional.

Do not make OCR room names a blocker.

---

# 12. Source / Provenance

Use three values:

```text
detected
estimated
inferred
```

Example:

```text
Wall detected by AI
        ↓
source = detected
```

```text
Missing wall connection repaired by topology
        ↓
source = inferred
```

```text
Wall height not present in floor plan
        ↓
source = estimated
```

This will help explain the reconstruction process during judging.

---

# 13. STEP 2 — Build the Pipeline

Create:

```text
integration/pipeline.py
```

Initial version:

```python
def reconstruct(input_path):

    masks = analyze_floorplan(input_path)

    scene = reconstruct_geometry(masks)

    scene = calibrate_scale(scene, input_path)

    validate_scene(scene)

    glb_path = generate_3d(scene)

    return {
        "scene": scene,
        "glb": glb_path
    }
```

The actual function names can change to match your teammates' implementation.

The architecture must remain:

```text
INPUT
 ↓
AI
 ↓
GEOMETRY
 ↓
SCALE
 ↓
VALIDATION
 ↓
3D
 ↓
GLB
```

---

# 14. STEP 3 — Build a CLI

Before building the API, create a command-line pipeline.

Create:

```text
scripts/run_pipeline.py
```

Run:

```bash
python scripts/run_pipeline.py data/input/floorplan_01.png
```

Expected output:

```text
Processing floorplan_01.png

[1/6] Preprocessing ........ OK
[2/6] AI segmentation ..... OK
[3/6] Geometry ............ OK
[4/6] Scale ............... OK
[5/6] Validation .......... OK
[6/6] 3D export ........... OK

Output:
outputs/floorplan_01/scene.json
outputs/floorplan_01/scene.glb
```

This CLI is more important than the web API.

If the API fails, the CLI keeps the project alive.

---

# 15. STEP 4 — Add FastAPI

Only after the CLI works.

Install:

```bash
pip install fastapi uvicorn python-multipart
```

Create:

```text
integration/api.py
```

Endpoint:

```text
POST /reconstruct
```

Input:

```text
multipart/form-data
file = floorplan.png
```

Response:

```json
{
  "success": true,
  "scene": "/outputs/floorplan_01/scene.json",
  "model": "/outputs/floorplan_01/scene.glb"
}
```

Run:

```bash
uvicorn integration.api:app --reload
```

---

# 16. STEP 5 — Input Validation

Before sending anything to Member 1, check:

### File exists

```python
if not input_path.exists():
    raise FileNotFoundError(...)
```

### Supported extension

```text
.png
.jpg
.jpeg
.pdf
```

### Image readable

Open using Pillow/OpenCV.

### Resolution

Warn if the image is extremely small.

### PDF

If PDF support is added, rasterize it before AI processing.

---

# 17. STEP 6 — Scale Calibration

This is your main technical responsibility besides integration.

The model needs real-world dimensions.

Possible sources:

```text
1. Explicit dimension on drawing
2. Known reference measurement
3. Estimated proportional scale
```

---

# 18. Scale Method A — Explicit Dimension

Suppose the drawing says:

```text
4500 mm
```

and the corresponding line is:

```text
300 pixels
```

Then:

```text
4500 mm / 300 px
=
15 mm/px
```

Therefore:

```text
0.015 m/px
```

Use:

```python
meters_per_pixel = real_length_m / pixel_length
```

---

# 19. Scale Method B — Reference Object

If a known architectural reference is available:

```text
reference width = 0.90 m
pixel width = 60 px
```

Then:

```text
scale = 0.90 / 60
      = 0.015 m/px
```

Store:

```json
{
  "value": 0.015,
  "source": "reference",
  "confidence": 0.70
}
```

---

# 20. Scale Method C — Estimated

If no reliable dimension exists:

```text
Use proportional geometry.
```

Do NOT pretend the dimensions are exact.

Store:

```json
{
  "value": 0.012,
  "source": "estimated",
  "confidence": 0.45
}
```

This is more honest and defensible.

---

# 21. Scale Validation

After calculating scale, check whether the resulting building dimensions are plausible.

Example:

```text
Room width = 0.15 m
```

This is suspicious.

Or:

```text
Building width = 800 m
```

Also suspicious.

Create sanity checks.

Example:

```python
if room_width < 1.0:
    warning("Unusually small room")

if building_width > 200:
    warning("Unusually large building")
```

These thresholds should be treated as sanity checks, not architectural truth.

---

# 22. STEP 7 — Scene Validation

Create:

```text
integration/validators.py
```

Check:

### Walls

- Are there walls?
- Do they have valid coordinates?
- Is thickness positive?
- Is height positive?

### Doors

- Does every door reference a real wall?
- Is width positive?
- Is position between 0 and 1?

### Windows

- Does every window reference a real wall?
- Is width positive?
- Is position between 0 and 1?

### Rooms

- Does the polygon have at least 3 points?
- Is the polygon valid?

---

# 23. Example Validator

```python
def validate_scene(scene):

    errors = []

    if len(scene["walls"]) == 0:
        errors.append("No walls detected")

    wall_ids = {
        wall["id"]
        for wall in scene["walls"]
    }

    for door in scene["doors"]:

        if door["wall_id"] not in wall_ids:
            errors.append(
                f'Door {door["id"]} references invalid wall'
            )

        if not 0 <= door["position"] <= 1:
            errors.append(
                f'Door {door["id"]} has invalid position'
            )

    if errors:
        return False, errors

    return True, []
```

---

# 24. STEP 8 — Baseline

The official problem statement requires the team to choose a baseline and beat it on held-out inputs.

For your 24-hour implementation, define a transparent baseline.

## Baseline

```text
Floor plan
 ↓
Pretrained segmentation
 ↓
Raw contour extraction
 ↓
Naive extrusion
 ↓
3D model
```

## Proposed

```text
Floor plan
 ↓
Pretrained segmentation
 ↓
Topology correction
 ↓
Wall continuity
 ↓
Door/window association
 ↓
Scale calibration
 ↓
Geometry validation
 ↓
3D model
```

The comparison should demonstrate whether your post-processing adds measurable value.

---

# 25. Do Not Claim an Improvement Without Measurement

Bad:

> Our method is 20% more accurate.

Good:

> On our held-out test set, the proposed topology correction reduced measured layout error from X to Y.

Only use actual values.

---

# 26. STEP 9 — Dataset Organization

Create:

```text
data/
├── development/
│   ├── plan_01.png
│   ├── plan_02.png
│   ├── plan_03.png
│   ├── plan_04.png
│   ├── plan_05.png
│   └── plan_06.png
│
├── heldout/
│   ├── plan_07.png
│   ├── plan_08.png
│   ├── plan_09.png
│   └── plan_10.png
│
└── demo/
    ├── demo_01.png
    ├── demo_02.png
    └── demo_03.png
```

Use development images for debugging.

Do NOT tune specifically against held-out images.

---

# 27. STEP 10 — Ground Truth

For every evaluation floor plan, create expected geometry where possible.

Example:

```json
{
  "walls": 18,
  "doors": 7,
  "windows": 11,
  "rooms": 6
}
```

If measured dimensions are available:

```json
{
  "building_width": 12.5,
  "building_length": 9.2
}
```

Do not invent ground truth.

Use actual measurements from the source/test setup.

---

# 28. STEP 11 — Evaluation Metrics

The official Mode A rubric specifically mentions:

- wall/door/window placement
- room dimensions
- layout IoU
- dimension error
- completeness
- model quality
- viewer usability
- research contribution

Your internal evaluation should therefore contain:

```text
1. Layout IoU
2. Placement error
3. Dimension error
4. Completeness
5. Geometry validity
6. Baseline comparison
```

---

# 29. Layout IoU

For masks:

```text
IoU = Intersection / Union
```

Example:

```text
Predicted wall mask
        ∩
Ground truth wall mask
        /
Predicted wall mask
        ∪
Ground truth wall mask
```

Calculate separately where ground truth masks are available.

Example:

```python
def iou(pred, gt):

    intersection = (pred & gt).sum()
    union = (pred | gt).sum()

    if union == 0:
        return 1.0

    return intersection / union
```

---

# 30. Placement Error

For a detected object:

```text
ground truth center
        vs
predicted center
```

Euclidean error:

```text
error =
sqrt(
    (x_pred - x_gt)^2 +
    (y_pred - y_gt)^2
)
```

Report:

```text
Mean wall placement error
Mean door placement error
Mean window placement error
```

---

# 31. Dimension Error

Formula:

```text
Absolute Error =
|predicted - actual|
```

Relative error:

```text
Relative Error (%) =
|predicted - actual|
-------------------- × 100
       actual
```

Example:

Actual:

```text
5.00 m
```

Predicted:

```text
5.20 m
```

Then:

```text
Absolute error = 0.20 m

Relative error =
0.20 / 5.00 × 100
= 4%
```

---

# 32. Completeness

Simple internal measure:

```text
Completeness =
Detected required components
----------------------------
Expected required components
```

Example:

Expected:

```text
20 walls
8 doors
10 windows
```

Detected:

```text
19 walls
8 doors
9 windows
```

You can report component-level recall.

Do not claim this is the official judging formula unless the organizers provide one.

---

# 33. Geometry Validation Metrics

Check:

```text
Invalid wall count
Disconnected wall count
Door-without-wall count
Window-without-wall count
Self-intersecting room count
```

Example:

```text
Baseline:
Disconnected walls = 7

Ours:
Disconnected walls = 2
```

This can provide strong evidence for the topology contribution.

---

# 34. STEP 12 — Evaluation Script

Create:

```text
evaluation/evaluate.py
```

Run:

```bash
python evaluation/evaluate.py
```

Expected:

```text
========================================
HNX26EPS06 EVALUATION
========================================

Plans evaluated: 4

LAYOUT
----------------------------------------
Wall IoU:
Door placement error:
Window placement error:

DIMENSIONS
----------------------------------------
Mean absolute error:
Mean relative error:

COMPLETENESS
----------------------------------------
Walls:
Doors:
Windows:
Rooms:

GEOMETRY
----------------------------------------
Disconnected walls:
Invalid doors:
Invalid windows:

BASELINE COMPARISON
----------------------------------------
Baseline score:
Proposed score:

========================================
```

---

# 35. STEP 13 — Save Machine-Readable Results

Create:

```text
evaluation/results/results.json
```

Example:

```json
{
  "plans_evaluated": 4,

  "baseline": {
    "wall_iou": 0.71,
    "dimension_error": 0.12
  },

  "proposed": {
    "wall_iou": 0.79,
    "dimension_error": 0.08
  }
}
```

Only populate with real measurements.

---

# 36. STEP 14 — Ablation Study

This is especially important because the official rubric allocates 20% to research contribution.

Do a simple ablation.

### Experiment A

```text
Segmentation only
+
naive extrusion
```

### Experiment B

```text
Segmentation
+
topology correction
+
extrusion
```

### Experiment C

```text
Segmentation
+
topology correction
+
scale calibration
+
validation
+
extrusion
```

Compare:

```text
A vs B vs C
```

This shows what your contribution actually adds.

---

# 37. Example Ablation Table

Use this structure:

| Pipeline | Wall IoU | Door Error | Dimension Error | Invalid Geometry |
|---|---:|---:|---:|---:|
| Baseline | measured | measured | measured | measured |
| + Topology | measured | measured | measured | measured |
| + Scale | measured | measured | measured | measured |
| Full | measured | measured | measured | measured |

Again:

**Never fabricate the values.**

---

# 38. STEP 15 — Integration Branch Strategy

You should be the person responsible for merging.

Branches:

```text
main

member1-ai
member2-geometry
member3-3d
member4-integration
```

You work primarily on:

```text
member4-integration
```

When someone finishes:

```bash
git checkout member4-integration
git merge member1-ai
```

Run tests.

Then:

```bash
git merge member2-geometry
```

Run tests.

Then:

```bash
git merge member3-3d
```

Run tests.

Only then merge to:

```text
main
```

---

# 39. Never Merge Blindly

After every merge:

```bash
python scripts/run_pipeline.py data/development/plan_01.png
```

Check:

```text
AI ✓
Geometry ✓
Scale ✓
Validation ✓
GLB ✓
Viewer ✓
```

If anything fails, fix it before the next merge.

---

# 40. Integration Contract With Member 1

Member 1 must provide:

```python
analyze_floorplan(path)
```

or an equivalent interface.

Expected:

```json
{
  "wall_mask": "...",
  "door_mask": "...",
  "window_mask": "...",
  "floor_mask": "..."
}
```

Do not care how Member 1 implemented the neural network.

You only care about the output.

---

# 41. Integration Contract With Member 2

Member 2 must provide:

```python
reconstruct_geometry(masks)
```

Expected:

```text
scene.json
```

Containing:

```text
walls
doors
windows
rooms
```

---

# 42. Integration Contract With Member 3

Member 3 must provide:

```python
generate_3d(scene)
```

Expected:

```text
scene.glb
```

The viewer must load the generated model.

---

# 43. Error Handling

Your pipeline should never fail silently.

Bad:

```text
Error.
```

Good:

```text
[ERROR] No walls detected.
Possible causes:
- unsupported floor-plan style
- segmentation failure
- low image quality

Saved intermediate masks to:
outputs/debug/
```

Always preserve intermediate outputs when debugging.

---

# 44. Debug Output

For every run:

```text
outputs/
└── plan_01/
    ├── original.png
    ├── processed.png
    ├── wall_mask.png
    ├── door_mask.png
    ├── window_mask.png
    ├── scene.json
    ├── scene.glb
    └── report.json
```

This makes debugging dramatically easier.

---

# 45. Report JSON

Example:

```json
{
  "input": "plan_01.png",

  "status": "success",

  "components": {
    "walls": 18,
    "doors": 7,
    "windows": 10,
    "rooms": 6
  },

  "scale": {
    "value": 0.015,
    "source": "reference",
    "confidence": 0.81
  },

  "validation": {
    "valid": true,
    "warnings": []
  },

  "output": {
    "scene": "scene.json",
    "model": "scene.glb"
  }
}
```

---

# 46. 24-HOUR TIMELINE FOR MEMBER 4

## Hour 0–1

### Must finish

- Repository setup
- Directory structure
- Scene JSON schema
- Branch
- Basic CLI

---

## Hour 1–3

### Must finish

- Pipeline skeleton
- Dummy masks
- Dummy scene
- Basic validation

Your pipeline should already execute:

```text
input → dummy → scene.json
```

---

## Hour 3–5

### Must finish

- Member 1 connection
- Member 2 connection
- First real scene JSON

---

## Hour 5–7

### Critical milestone

Full pipeline:

```text
floorplan
 ↓
AI
 ↓
geometry
 ↓
scene.json
 ↓
3D
 ↓
GLB
```

If this doesn't work by Hour 7:

**Stop adding features.**

Focus only on integration.

---

## Hour 7–9

Work on:

- scale
- validation
- error handling
- debug outputs

---

## Hour 9–12

Build baseline.

Run:

```text
baseline
vs
proposed
```

---

## Hour 12–15

Build held-out evaluation.

Do not tune against held-out data.

---

## Hour 15–17

Run ablation:

```text
baseline
topology
topology + scale
full
```

---

## Hour 17–19

Prepare:

- evaluation tables
- graphs
- architecture diagram
- technical explanation

---

## Hour 19–21

Freeze code.

Test:

- 3 demo plans
- 4 held-out plans
- clean restart
- viewer

---

## Hour 21–23

Prepare:

- README
- presentation evidence
- demo script
- backup outputs

---

## Hour 23–24

NO NEW FEATURES.

Only:

```text
test
fix
test
backup
test
```

---

# 47. Demo Dataset

Prepare three excellent examples.

### Demo 1

Simple:

```text
2–3 rooms
```

Purpose:

Show that the system works.

### Demo 2

Medium:

```text
5–8 rooms
```

Purpose:

Show scalability.

### Demo 3

Messy:

```text
many walls
doors
windows
annotations
```

Purpose:

Show robustness.

Do not choose only perfect floor plans.

---

# 48. Backup Plan

Before judging:

```text
backup/
├── model_weights/
├── demo_inputs/
├── demo_outputs/
├── source_code/
├── environment.txt
└── presentation.pdf
```

Also keep:

```text
scene.glb
```

for each demo.

If live AI inference fails, you should still be able to show the generated 3D result.

---

# 49. Final Demo Flow

You control the technical demo.

## Step 1

Show floor plan.

Say:

> "This is our 2D architectural input."

## Step 2

Upload.

## Step 3

Show segmentation.

Say:

> "Our semantic stage identifies architectural components such as walls, doors and windows."

## Step 4

Show topology processing.

Say:

> "Instead of directly extruding noisy segmentation, we construct a geometry-aware scene graph and correct disconnected or misaligned components."

## Step 5

Show scale.

Say:

> "Where reliable dimensional information is available, we calibrate the reconstructed geometry; otherwise the system reports estimated scale."

## Step 6

Show 3D model.

## Step 7

Orbit around.

## Step 8

Show dimensions.

## Step 9

Show baseline vs proposed.

## Step 10

Show evaluation.

---

# 50. Questions Judges May Ask You

## Q1. What is your baseline?

Answer:

> "We use a direct segmentation-to-extrusion pipeline as our baseline. Our proposed pipeline adds topology correction, architectural component association, scale calibration and validation before 3D generation."

---

## Q2. What is actually new?

Answer:

> "Our contribution is the geometry-aware reconstruction layer rather than simply applying a segmentation model. We enforce architectural relationships between walls, doors and windows and validate the resulting scene before extrusion."

---

## Q3. Did you train your own model?

Do not lie.

If you used pretrained weights:

> "We use pretrained floor-plan segmentation because the 24-hour constraint makes training a new model impractical. Our work focuses on the reconstruction and geometry pipeline around the segmentation model."

---

## Q4. How do you handle missing dimensions?

Answer:

> "We distinguish measured or reference-derived scale from estimated scale and expose the confidence/source rather than presenting an estimate as ground truth."

---

## Q5. How do you know your system is better?

Answer:

> "We evaluate on held-out floor plans and compare our geometry-aware pipeline against the direct baseline using layout, placement, dimension and completeness measurements."

---

## Q6. What happens if segmentation is wrong?

Answer:

> "The topology and validation stages attempt to correct structural inconsistencies, while the system preserves intermediate outputs so failure cases can be identified rather than silently producing invalid geometry."

---

# 51. Your Personal Checklist

## Setup

- [ ] Clone repository
- [ ] Create branch
- [ ] Create directories
- [ ] Create Python environment
- [ ] Install dependencies
- [ ] Create scene schema

## Integration

- [ ] AI interface defined
- [ ] Geometry interface defined
- [ ] 3D interface defined
- [ ] CLI works
- [ ] Pipeline works
- [ ] API works

## Scale

- [ ] Dimension extraction
- [ ] Reference scale
- [ ] Estimated scale
- [ ] Confidence/source field
- [ ] Sanity checks

## Validation

- [ ] Wall validation
- [ ] Door validation
- [ ] Window validation
- [ ] Room validation
- [ ] Scene validation

## Evaluation

- [ ] Development dataset
- [ ] Held-out dataset
- [ ] Baseline
- [ ] Layout metric
- [ ] Dimension metric
- [ ] Completeness metric
- [ ] Ablation

## Release

- [ ] Demo inputs
- [ ] Demo outputs
- [ ] GLB files
- [ ] Viewer
- [ ] README
- [ ] Architecture diagram
- [ ] Evaluation table
- [ ] Backup
- [ ] Final test

---

# 52. Definition of DONE

Member 4 is finished only when this command works:

```bash
python scripts/run_pipeline.py data/demo/demo_01.png
```

and produces:

```text
outputs/demo_01/
├── scene.json
├── scene.glb
└── report.json
```

and the 3D viewer successfully loads:

```text
scene.glb
```

AND:

```bash
python evaluation/evaluate.py
```

produces a real evaluation report.

---

# 53. Your Priority Order

If time becomes limited, use this order:

```text
P0
│
├── Integration
├── End-to-end pipeline
├── GLB generation
└── Viewer
│
P1
│
├── Scale
├── Validation
└── Baseline
│
P2
│
├── Held-out evaluation
├── Ablation
└── Research graphs
│
P3
│
├── Fancy UI
├── Advanced OCR
└── Extra features
```

Never sacrifice P0 for P3.

---

# 54. Final Responsibility

Remember:

Member 1 makes the computer **see** the floor plan.

Member 2 makes the computer **understand the geometry**.

Member 3 makes the geometry **become 3D**.

**You make the entire system actually work.**

Your final responsibility is:

```text
                 FLOOR PLAN
                     │
                     ▼
               AI SEGMENTATION
                     │
                     ▼
              GEOMETRY ENGINE
                     │
                     ▼
              SCALE + VALIDATION
                     │
                     ▼
                3D GENERATOR
                     │
                     ▼
                  GLB MODEL
                     │
                     ▼
               3D VIEWER
                     │
                     ▼
                 EVALUATION
                     │
                     ▼
              JUDGING EVIDENCE
```

## Your objective for the 24 hours

> **Make the pipeline reliable, measurable and defensible.**

Not just functional.

Not just visually impressive.

It must be possible to explain **what the system did, why it did it, and whether it improved over the baseline.**
