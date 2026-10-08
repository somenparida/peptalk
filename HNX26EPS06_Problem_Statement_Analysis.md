# HNX26EPS06 --- 3D Scene Generation from Blueprints and Room Video

## 1. Problem Overview

**HNX26EPS06: 3D Scene Generation from Blueprints and Room Video**

The goal is to take information about a **static room/building** and
automatically generate a **usable 3D model**.

There are two possible input modes:

  -----------------------------------------------------------------------
  Mode                    Input                   Output
  ----------------------- ----------------------- -----------------------
  **Mode A**              2D architectural        3D room/building model
                          blueprint / floor plan  

  **Mode B**              Video/photos of a room  3D reconstructed scene
  -----------------------------------------------------------------------

The system should not merely reproduce what the camera sees. It should
also **complete unseen parts of the room**, while clearly distinguishing
observed geometry from generated geometry.

------------------------------------------------------------------------

## 2. Core Challenge

A camera only captures part of a room. The system must reconstruct the
visible geometry and intelligently infer/complete areas that were never
observed.

The key challenge is therefore:

**Visual/2D information → spatial understanding → 3D reconstruction →
missing-region completion → trustworthy visualization**

The problem is harder than ordinary 3D reconstruction because the system
must be honest about which parts are actually observed and which parts
are generated.

------------------------------------------------------------------------

## 3. Mode A --- Floor Plan → 3D Model

### Input

A 2D architectural blueprint/floor plan containing elements such as:

-   Walls
-   Doors
-   Windows
-   Room boundaries
-   Dimensions
-   Openings
-   Relative positions

### Processing

``` text
Floor Plan
    ↓
Plan Understanding
    ↓
Wall / Door / Window Detection
    ↓
Dimension Extraction
    ↓
Semantic Scene Graph
    ↓
Parametric 3D Generation
    ↓
Interactive 3D Viewer
```

### Output

A geometrically accurate 3D representation of the building/room that can
be:

-   Rotated
-   Zoomed
-   Panned
-   Inspected in a real 3D viewer
-   Exported to a standard 3D format

------------------------------------------------------------------------

## 4. Mode B --- Room Video → 3D Scene

### Input

A short video or collection of room images.

### Suggested Pipeline

``` text
Room Video
    ↓
Frame Extraction
    ↓
Camera Pose Estimation / COLMAP
    ↓
Point Cloud / 3D Reconstruction
    ↓
3D Gaussian Splatting / NeRF
    ↓
Unseen Region Detection
    ↓
Generative Completion
    ↓
Confidence / Observed-vs-Generated Map
    ↓
Interactive 3D Viewer
```

Mode B is significantly harder because accurate geometry and
unseen-region completion must both be handled.

------------------------------------------------------------------------

## 5. Judging Rubric

### Mode A --- Floor Plan → 3D Model

  Evaluation                  Weight
  ----------------------- ----------
  Layout accuracy            **40%**
  Completeness               **15%**
  Model quality              **15%**
  3D viewer usability        **10%**
  Research contribution      **20%**
  **Total**                 **100%**

### What matters most

**Layout accuracy --- 40%**

The generated model must correctly place:

-   Walls
-   Doors
-   Windows
-   Room dimensions

Therefore, **correct geometry is more important than fancy graphics**.

------------------------------------------------------------------------

## 6. Mode B --- Room Video → 3D Scene

  Evaluation                              Weight
  ----------------------------------- ----------
  Novel-view quality                     **20%**
  Geometric accuracy                     **25%**
  Generated unseen regions               **15%**
  Observed vs. generated separation      **15%**
  3D viewer usability                     **5%**
  Research contribution                  **20%**
  **Total**                             **100%**

The most important areas are:

### Geometric accuracy --- 25%

The reconstructed room should have accurate:

-   Dimensions
-   Walls
-   Corners
-   Floor
-   Ceiling
-   Objects

### Novel-view quality --- 20%

When the judge moves the camera to a viewpoint that was not directly
present in the input video, the scene should still look realistic.

------------------------------------------------------------------------

## 7. Observed vs. Generated Geometry

The problem specifically values **honesty**.

The system should clearly indicate which regions were actually observed
and which were generated.

Example:

``` text
GREEN = Observed geometry
RED   = AI-generated geometry
```

Possible implementations:

-   Confidence map
-   Color overlay
-   Transparent generated geometry
-   Different materials
-   Viewer toggle:
    -   Observed
    -   Generated
    -   Both

This is especially important for Mode B.

------------------------------------------------------------------------

## 8. Research Contribution

Simply using an existing pipeline such as:

``` text
Video → COLMAP → 3DGS
```

is unlikely to be enough.

The team should demonstrate a measurable improvement over the baseline.

### Example

#### Baseline

``` text
Video
  ↓
COLMAP
  ↓
3D Gaussian Splatting
  ↓
Incomplete Room
```

#### Proposed Method

``` text
Video
  ↓
COLMAP
  ↓
3D Gaussian Splatting
  ↓
Room Structure Detection
  ↓
Unseen Region Detection
  ↓
Geometry-Aware Completion
  ↓
Confidence Estimation
  ↓
Completed 3D Scene
```

The additional processing can become the team's **research
contribution**.

------------------------------------------------------------------------

## 9. Recommended Solution Architecture

For a 24-hour hackathon, a practical architecture is:

``` text
                 ┌──────────────────┐
                 │   Input Upload   │
                 └────────┬─────────┘
                          │
                    Detect Input
                     /          \
                    /            \
             Floor Plan          Video
                 │                 │
                 ▼                 ▼
           Plan Parser          Frames
                 │                 │
                 ▼                 ▼
       Wall/Door/Window         COLMAP
            Detection             │
                 │                 ▼
                 ▼               3DGS
          Scene Graph              │
                 │                 │
                 └───────┬────────┘
                         ▼
                  Geometry Engine
                         │
                         ▼
              Unseen Region Detection
                         │
                         ▼
               Generative Completion
                         │
                         ▼
                  Confidence Map
                         │
                         ▼
                    3D Viewer
```

------------------------------------------------------------------------

## 10. Recommended Technology Stack

### Mode A

**Programming**

-   Python
-   OpenCV
-   Open3D

**Floor-plan understanding**

-   OpenCV line detection
-   Hough Transform
-   Contour detection
-   OCR for dimensions
-   Optional vision-language model for semantic interpretation

**3D generation**

-   Blender Python API
-   Open3D
-   Three.js

### Mode B

Recommended technologies:

-   COLMAP / Structure-from-Motion
-   3D Gaussian Splatting
-   Open3D
-   Three.js

------------------------------------------------------------------------

## 11. Best Hackathon Strategy

The problem explicitly allows teams to **pick one mode**.

For a 24-hour implementation, **Mode A is the safer choice**.

  Factor                      Mode A       Mode B
  --------------------------- ------------ ------------
  Implementation difficulty   Medium       Very High
  Dataset requirement         Easy         Hard
  Geometry accuracy           Easier       Hard
  Unseen completion           Manageable   Difficult
  24-hour feasibility         ⭐⭐⭐⭐⭐   ⭐⭐⭐
  Demo reliability            ⭐⭐⭐⭐⭐   ⭐⭐⭐
  Research potential          ⭐⭐⭐⭐     ⭐⭐⭐⭐⭐

### Recommended priority

**Choose Mode A first**, then add Mode B only if the core pipeline is
already working.

------------------------------------------------------------------------

## 12. Strong Unique Idea --- Semantic 3D Scene Graph

Instead of directly converting a blueprint into arbitrary 3D geometry,
first convert it into a structured scene representation.

Example:

``` json
{
  "room": {
    "width": 5.2,
    "length": 4.1,
    "height": 3.0
  },
  "walls": [],
  "doors": [],
  "windows": [],
  "objects": []
}
```

Then generate the 3D model from this structured representation.

This creates a robust pipeline:

``` text
Blueprint
    ↓
Semantic Layout
    ↓
Structured Scene Graph
    ↓
Parametric 3D Model
```

This makes validation and measurement easier.

------------------------------------------------------------------------

## 13. Suggested Final Demo

### Step 1 --- Upload

``` text
┌─────────────────────────┐
│ Upload Floor Plan       │
│                         │
│      blueprint.png      │
│                         │
│       [Generate]        │
└─────────────────────────┘
```

### Step 2 --- AI Interpretation

``` text
Walls       ✓
Doors       ✓
Windows     ✓
Dimensions  ✓
Rooms       ✓
```

### Step 3 --- 3D Generation

``` text
Generating 3D scene...

████████████████░░ 82%
```

### Step 4 --- Interactive Viewer

``` text
┌─────────────────────────────────┐
│                                 │
│          3D ROOM                │
│                                 │
│      [Orbit] [Zoom] [Pan]       │
│                                 │
│  Observed 🟩  Generated 🟥      │
└─────────────────────────────────┘
```

### Step 5 --- Evaluation Dashboard

Show measurable results:

``` text
Original Blueprint       Generated 3D

Dimension Error: 2.1%
Layout IoU:       94%
Doors:            4/4
Windows:          6/6
Rooms:            5/5
```

This directly targets the judging rubric.

------------------------------------------------------------------------

## 14. What the Problem Is Really Asking

In one sentence:

> **Build an AI system that understands a 2D floor plan or room video,
> reconstructs the room as a geometrically accurate 3D scene,
> intelligently fills areas that were never observed, and lets judges
> inspect the result interactively.**

The core research problem is not simply 3D modeling.

It is:

**2D/visual information → spatial understanding → 3D reconstruction →
missing-region completion → trustworthy visualization**

------------------------------------------------------------------------

## 15. Final Recommendation

For a 24-hour hackathon:

### Primary choice

**Mode A --- Floor Plan → 3D Model**

### Main pipeline

``` text
Floor Plan
    ↓
Wall / Door / Window Detection
    ↓
Dimension Extraction
    ↓
Semantic Scene Graph
    ↓
Parametric 3D Generation
    ↓
Three.js 3D Viewer
    ↓
Accuracy + Confidence Dashboard
```

### Main scoring targets

1.  **Layout accuracy --- 40%**
2.  **Research contribution --- 20%**
3.  **Completeness --- 15%**
4.  **Model quality --- 15%**
5.  **3D viewer usability --- 10%**

Focus on **measurable geometric accuracy and a clear research
improvement over the baseline**, rather than spending most of the 24
hours on UI effects.
