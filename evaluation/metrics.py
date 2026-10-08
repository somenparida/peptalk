import math
from typing import List, Tuple, Optional, Dict, Any
import numpy as np
import cv2
from scipy.optimize import linear_sum_assignment

from integration.config import (
    WEIGHT_IOU,
    WEIGHT_DIMENSION,
    WEIGHT_COMPLETENESS,
    WEIGHT_VALIDITY,
)


def iou(pred: np.ndarray, gt: np.ndarray) -> float:
    """Compute Intersection over Union (IoU) of two binary masks."""
    pred_bin = (pred > 0).astype(np.uint8)
    gt_bin = (gt > 0).astype(np.uint8)

    inter = float(np.logical_and(pred_bin, gt_bin).sum())
    union = float(np.logical_or(pred_bin, gt_bin).sum())

    if union == 0.0:
        return 1.0
    return inter / union


def rasterize_walls_to_mask(
    walls: List[Dict[str, Any]],
    shape: Tuple[int, int],
    mpp: float = 0.015
) -> np.ndarray:
    """Rasterize scene walls into a binary image mask."""
    h, w = shape
    mask = np.zeros((h, w), dtype=np.uint8)

    for wall in walls:
        p1 = wall["start"]
        p2 = wall["end"]
        th_m = wall.get("thickness", 0.20)

        # Convert meters to pixel coordinates
        x1, y1 = int(round(p1[0] / mpp)), int(round(p1[1] / mpp))
        x2, y2 = int(round(p2[0] / mpp)), int(round(p2[1] / mpp))
        th_px = max(1, int(round(th_m / mpp)))

        cv2.line(mask, (x1, y1), (x2, y2), 255, thickness=th_px)

    return mask


def placement_error(
    pred_xy: List[Tuple[float, float]],
    gt_xy: List[Tuple[float, float]]
) -> Optional[float]:
    """
    Compute mean placement error in meters using Hungarian matching
    (scipy.optimize.linear_sum_assignment).
    """
    if not pred_xy or not gt_xy:
        return None

    n_pred = len(pred_xy)
    n_gt = len(gt_xy)

    cost_matrix = np.zeros((n_pred, n_gt), dtype=np.float64)
    for i, (px, py) in enumerate(pred_xy):
        for j, (gx, gy) in enumerate(gt_xy):
            cost_matrix[i, j] = math.hypot(px - gx, py - gy)

    row_ind, col_ind = linear_sum_assignment(cost_matrix)
    matched_costs = cost_matrix[row_ind, col_ind]

    return float(np.mean(matched_costs)) if len(matched_costs) > 0 else None


def abs_error(pred: float, actual: float) -> float:
    return abs(pred - actual)


def rel_error_pct(pred: float, actual: float) -> Optional[float]:
    if actual == 0:
        return None
    return abs(pred - actual) / actual * 100.0


def recall(detected: int, expected: int) -> Optional[float]:
    if expected <= 0:
        return None
    return float(detected) / float(expected)


def compute_composite_score(
    iou_val: Optional[float],
    dim_rel_error: Optional[float],
    completeness_recall: Optional[float],
    validity_counters: Dict[str, int]
) -> float:
    """
    Compute composite score [0 .. 100].
    Weights: IoU 40%, Dimension 25%, Completeness 20%, Validity 15%
    """
    score = 0.0
    tot_weight = 0.0

    if iou_val is not None:
        score += WEIGHT_IOU * (iou_val * 100.0)
        tot_weight += WEIGHT_IOU

    if dim_rel_error is not None:
        dim_score = max(0.0, 100.0 - dim_rel_error)
        score += WEIGHT_DIMENSION * dim_score
        tot_weight += WEIGHT_DIMENSION

    if completeness_recall is not None:
        score += WEIGHT_COMPLETENESS * (completeness_recall * 100.0)
        tot_weight += WEIGHT_COMPLETENESS

    if validity_counters is not None:
        total_invalids = sum(validity_counters.values())
        val_score = max(0.0, 100.0 - 10.0 * total_invalids)
        score += WEIGHT_VALIDITY * val_score
        tot_weight += WEIGHT_VALIDITY

    if tot_weight == 0.0:
        return 0.0

    return round(score / tot_weight, 2)
