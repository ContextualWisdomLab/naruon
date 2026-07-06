from services.ai_grounding_eval import compute_grounding_metrics


def test_compute_grounding_metrics_typical():
    metrics = compute_grounding_metrics(
        confidences=[0.9, 0.4, 0.8, 0.3],
        citation_counts=[2, 0, 1, 1],
        correction_count=1,
    )
    assert metrics.total_objects == 4
    assert metrics.grounded_objects == 3  # citation_counts > 0
    assert metrics.grounding_rate == 0.75
    assert metrics.low_confidence_objects == 2  # 0.4 and 0.3 are below 0.5
    assert abs(metrics.mean_confidence - 0.6) < 1e-9
    assert metrics.correction_count == 1
    assert metrics.correction_rate == 0.25
    assert metrics.as_score() == 75


def test_compute_grounding_metrics_all_grounded():
    metrics = compute_grounding_metrics(
        confidences=[0.7, 0.9],
        citation_counts=[1, 3],
        correction_count=0,
    )
    assert metrics.grounding_rate == 1.0
    assert metrics.low_confidence_objects == 0
    assert metrics.as_score() == 100


def test_compute_grounding_metrics_empty_is_safe():
    metrics = compute_grounding_metrics(
        confidences=[], citation_counts=[], correction_count=0
    )
    assert metrics.total_objects == 0
    assert metrics.grounding_rate == 0.0
    assert metrics.mean_confidence == 0.0
    assert metrics.correction_rate == 0.0
    assert metrics.as_score() == 0
