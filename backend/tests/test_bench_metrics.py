import math

import pytest

from benchmarks.metrics import (
    dedupe_preserving_order,
    mrr_at_k,
    ndcg_at_k,
    overlap_recall,
    percentile,
    recall_at_k,
)


def test_recall_at_k() -> None:
    assert recall_at_k(["a", "x", "b"], {"a": 1, "b": 2, "c": 1}, k=3) == pytest.approx(2 / 3)
    assert recall_at_k(["a", "x", "b"], {"a": 1, "b": 1}, k=1) == 0.5
    assert recall_at_k(["a"], {"a": 0}, k=1) == 0.0  # grade 0 = not relevant


def test_ndcg_perfect_and_worst() -> None:
    relevant = {"a": 2, "b": 1}
    assert ndcg_at_k(["a", "b", "x"], relevant, k=3) == pytest.approx(1.0)
    assert ndcg_at_k(["x", "y"], relevant, k=2) == 0.0
    # b before a is worse than the ideal order
    assert 0 < ndcg_at_k(["b", "a"], relevant, k=2) < 1


def test_ndcg_known_value() -> None:
    # One relevant doc (gain 1) at rank 2: DCG = 1/log2(3), IDCG = 1
    assert ndcg_at_k(["x", "a"], {"a": 1}, k=10) == pytest.approx(1 / math.log2(3))


def test_mrr() -> None:
    assert mrr_at_k(["x", "y", "a"], {"a": 1}, k=10) == pytest.approx(1 / 3)
    assert mrr_at_k(["x", "y", "a"], {"a": 1}, k=2) == 0.0


def test_overlap_recall() -> None:
    assert overlap_recall([1, 2, 3, 9], [1, 2, 3, 4], k=4) == 0.75
    assert overlap_recall([4, 3, 2, 1], [1, 2, 3, 4], k=4) == 1.0  # order doesn't matter


def test_percentile_matches_linear_interpolation() -> None:
    values = list(range(1, 101))  # 1..100
    assert percentile(values, 50) == pytest.approx(50.5)
    assert percentile(values, 95) == pytest.approx(95.05)
    assert percentile([7.0], 99) == 7.0


def test_dedupe_preserving_order() -> None:
    assert dedupe_preserving_order(["a", "b", "a", "c", "b"]) == ["a", "b", "c"]
