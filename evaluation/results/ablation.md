# Ablation Study Results
**Split evaluated:** heldout  
**Total plans:** 4

| Pipeline Stage | Wall IoU | Dim Error (m) | Dim Rel Error (%) | Invalid Geometry | Composite Score |
|---|---:|---:|---:|---:|---:|
| Baseline (Naive Contour Extrusion) | n/a | 2.015 | 26.96% | 0.00 | 99.87 |
| + Topology Correction | n/a | 1.411 | 18.87% | 0.50 | 92.59 |
| + Scale Calibration | n/a | 0.671 | 9.50% | 0.00 | 81.03 |
| Full (Topology + Scale + Validation) | n/a | 0.610 | 8.64% | 0.00 | 85.30 |
