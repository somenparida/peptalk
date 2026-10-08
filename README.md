# HNX26EPS06 — 3D Scene Generation Backend Service

This repository contains the backend service, integration pipeline, scale calibration engine, scene validator, naive baseline, evaluation suite, and REST API for **HNX26EPS06 (Mode A: Floor Plan → 3D Model GLB)**.

---

## 🚀 Key Capabilities

- **FastAPI REST API**: High-performance backend endpoints for floor plan reconstruction and 3D model serving.
- **Resilient Adapter System**: Automatically integrates teammate modules (`ai/`, `geometry/`, `reconstruction/`) with instant fallback stubs when modules are absent.
- **Multi-Method Scale Calibration**:
  - **Explicit OCR**: Text extraction via EasyOCR / PyTesseract matched with Hough line segments.
  - **Reference Door**: Standard door width (0.90 m) calibration.
  - **Estimated Heuristic**: Wall thickness bounding box scaling.
- **Scene Geometry Validator**: Enforces schema validity, wall continuity, orphan item detection, and polygon integrity.
- **Evaluation & Benchmark Suite**: Layout IoU, Hungarian placement error, dimension MAE/MAPE %, completeness recall, composite benchmark scoring, and ablation study generation.

---

## 📁 Repository Structure

```text
├── ai/                      (Member 1 — AI segmentation module interface)
├── geometry/                (Member 2 — Geometry engine module interface)
├── reconstruction/          (Member 3 — 3D extrusion module interface)
├── viewer/                  (Member 3 — Three.js web viewer interface)
├── integration/
│   ├── api.py               (FastAPI REST server: /reconstruct, /health, /outputs)
│   ├── pipeline.py          (Main pipeline orchestrator)
│   ├── schemas.py           (Pydantic v2 data models & Scene.load/save)
│   ├── scale.py             (Scale calibration engine)
│   ├── validators.py        (Input sanity & scene topology validators)
│   ├── stubs.py             (Standalone fallback stubs)
│   ├── adapters.py          (Dynamic module loaders)
│   └── config.py            (System constants & composite weights)
├── evaluation/
│   ├── baseline.py          (Naive contour extrusion baseline engine)
│   ├── metrics.py           (Layout IoU, Hungarian matching, dimension MAPE, recall)
│   ├── evaluate.py          (Evaluation runner for development/heldout splits)
│   ├── ablation.py          (Ablation experiment generator)
│   ├── compare.py           (Matplotlib chart renderer)
│   └── results/             (Evaluation reports, ablation.md, comparison_charts.png)
├── data/
│   ├── development/         (plan_01 .. plan_06)
│   ├── heldout/             (plan_07 .. plan_10)
│   ├── demo/                (demo_01, demo_02, demo_03)
│   └── expected/            (Ground-truth JSON files per plan)
├── scripts/
│   ├── run_pipeline.py      (CLI runner)
│   ├── evaluate_all.py      (Master evaluation suite runner)
│   ├── check_dataset.py     (Ground truth coverage analyzer)
│   └── backup.py            (Release backup zip packager)
├── tests/                   (Pytest unit and integration test suite)
├── scene_schema.json        (JSON Schema Draft-07 common contract)
├── requirements.txt
└── README.md
```

---

## 🛠️ Installation & Setup

```bash
# Install Python dependencies
pip install -r requirements.txt
```

---

## ⚡ API Endpoints (FastAPI)

To start the FastAPI backend server:

```bash
uvicorn integration.api:app --reload --port 8000
```

### 1. Health Check
`GET http://localhost:8000/health`

Response:
```json
{
  "status": "ok",
  "implementations": {
    "ai": "real|stub",
    "geometry": "real|stub",
    "3d": "real|stub"
  }
}
```

### 2. Reconstruct Floor Plan
`POST http://localhost:8000/reconstruct`

- **Content-Type**: `multipart/form-data`
- **Body**:
  - `file`: Floor plan image file (`.png`, `.jpg`, `.jpeg`, `.pdf`)
  - `mode`: `"proposed"` (default) or `"baseline"`

Response:
```json
{
  "success": true,
  "scene": "/outputs/demo_01/scene.json",
  "model": "/outputs/demo_01/scene.glb",
  "report": "/outputs/demo_01/report.json",
  "warnings": []
}
```

### 3. Static Output Serving
`GET http://localhost:8000/outputs/<plan_name>/scene.glb`  
`GET http://localhost:8000/outputs/<plan_name>/scene.json`  

---

## 💻 CLI & Evaluation Usage

```bash
# Run proposed reconstruction on a floor plan image
python scripts/run_pipeline.py data/demo/demo_01.png

# Run naive baseline comparison
python scripts/run_pipeline.py data/demo/demo_01.png --baseline

# Run full evaluation & ablation study suite
python scripts/evaluate_all.py

# Run pytest unit tests
PYTHONPATH=. pytest -v tests/
```

---

## 🤝 Teammate Integration Interfaces

Place teammates' code in their respective folders:

- **Member 1 (AI Segmentation)**: Place in `ai/inference.py` -> function `analyze_floorplan(image_path) -> dict` returning masks `{"wall_mask", "door_mask", "window_mask", "floor_mask"}`.
- **Member 2 (Geometry Engine)**: Place in `geometry/reconstruction.py` -> function `reconstruct_geometry(masks) -> scene_dict`.
- **Member 3 (3D Extrusion)**: Place in `reconstruction/export.py` -> function `generate_3d(scene_dict, out_path) -> out_path`.
