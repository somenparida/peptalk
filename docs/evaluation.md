# Evaluation Methodology & Metrics — HNX26EPS06

## Evaluation Criteria & Weights

| Metric | Weight | Description |
|---|---:|---|
| **Layout IoU** | 40% | Rasterized wall mask intersection-over-union in ground-truth frame |
| **Dimension Error** | 25% | Mean Absolute Error (m) & Relative Error (%) on building/room dimensions |
| **Completeness Recall** | 20% | Per-component recall (`detected / expected` count) |
| **Geometry Validity** | 15% | Penalty score based on disconnected walls & bounds errors |

## Metric Formulas

1. **Layout IoU**:
   $$\text{IoU} = \frac{\sum (\text{Pred} \land \text{GT})}{\sum (\text{Pred} \lor \text{GT})}$$

2. **Placement Error (Hungarian Matching)**:
   $$\text{Error} = \frac{1}{N} \sum_{i=1}^{N} \sqrt{(x_i^{\text{pred}} - x_i^{\text{gt}})^2 + (y_i^{\text{pred}} - y_i^{\text{gt}})^2}$$

3. **Relative Error (%)**:
   $$\text{MAPE} = \frac{|\text{Pred} - \text{GT}|}{\text{GT}} \times 100$$

4. **Composite Score**:
   $$\text{Score} = 0.40 \cdot (\text{IoU} \times 100) + 0.25 \cdot \max(0, 100 - \text{MAPE}) + 0.20 \cdot (\text{Recall} \times 100) + 0.15 \cdot \max(0, 100 - 10 \cdot \text{Invalids})$$
