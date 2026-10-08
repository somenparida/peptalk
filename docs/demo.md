# Presentation & Demo Flow Script

## Step-by-Step Demo Flow

1. **Show Floor Plan Input**:
   - "This is our 2D architectural floor plan input (`demo_01.png`)."
2. **Execute Reconstruction**:
   - Run `python scripts/run_pipeline.py data/demo/demo_01.png`.
3. **Show Segmentation Stage**:
   - "Our semantic AI stage identifies walls, doors, windows, and floor regions."
4. **Show Topology & Scale Calibration**:
   - "We extract explicit text dimensions via OCR or fall back to standard door references. In this run, scale was calibrated at 0.0225 m/px with reference door width."
5. **Show Scene JSON & 3D Extrusion**:
   - "The geometry engine enforces wall continuity and outputs a schema-validated `scene.json` and `scene.glb` model."
6. **Orbit & View in 3D**:
   - Open Three.js web viewer / FastAPI static endpoint `/outputs/demo_01/scene.glb`.
7. **Show Benchmark & Baseline Comparison**:
   - Run `python scripts/evaluate_all.py` to display held-out benchmark and ablation study graphs.

## Judge Q&A Cheat Sheet

| Question | Recommended Answer |
|---|---|
| **What is your baseline?** | Direct contour segmentation to naive extrusion without topology repair, scale calibration, or bounds validation. |
| **What is new in your contribution?** | The geometry-aware reconstruction layer that enforces architectural continuity, calibrates scale, and validates bounds before 3D export. |
| **How do you handle missing scale?** | Multi-method calibration: Method A (OCR explicit text), Method B (reference door width), Method C (estimated fallback with confidence scores). |
| **How do you prove it's better?** | Held-out dataset evaluation measuring layout IoU, placement error, dimension MAPE %, and geometry validity. |
