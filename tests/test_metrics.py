import numpy as np
from evaluation.metrics import (
    iou,
    abs_error,
    rel_error_pct,
    recall,
    placement_error,
    compute_composite_score,
)


def test_iou_identical():
    m = np.ones((50, 50), dtype=np.uint8)
    assert iou(m, m) == 1.0


def test_rel_error_pct():
    assert abs(rel_error_pct(5.2, 5.0) - 4.0) < 1e-5


def test_recall():
    assert recall(19, 20) == 0.95
    assert recall(5, 0) is None


def test_placement_error():
    err = placement_error([(0, 0), (5, 5)], [(0.1, 0.1), (5.2, 5.0)])
    assert err is not None
    assert 0.1 <= err <= 0.3


def test_composite_score():
    score = compute_composite_score(
        iou_val=0.85,
        dim_rel_error=5.0,
        completeness_recall=0.90,
        validity_counters={"disconnected_walls": 0}
    )
    assert 80.0 <= score <= 100.0
