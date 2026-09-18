"""
Standard information-retrieval metrics. Definitions follow BEIR / TREC conventions
so results are comparable with published numbers.
"""

import math
from collections.abc import Mapping, Sequence


def recall_at_k(retrieved: Sequence[str], relevant: Mapping[str, int] | set[str], k: int) -> float:
    """Share of relevant items that appear in the top k (graded labels > 0 count as relevant)."""
    relevant_ids = _relevant_ids(relevant)
    if not relevant_ids:
        return 0.0
    return len(relevant_ids.intersection(retrieved[:k])) / len(relevant_ids)


def ndcg_at_k(retrieved: Sequence[str], relevant: Mapping[str, int], k: int) -> float:
    """Normalised discounted cumulative gain with graded relevance (gain = label)."""
    dcg = sum(relevant.get(doc_id, 0) / math.log2(rank + 2) for rank, doc_id in enumerate(retrieved[:k]))
    ideal_gains = sorted((g for g in relevant.values() if g > 0), reverse=True)[:k]
    idcg = sum(gain / math.log2(rank + 2) for rank, gain in enumerate(ideal_gains))
    return dcg / idcg if idcg > 0 else 0.0


def mrr_at_k(retrieved: Sequence[str], relevant: Mapping[str, int] | set[str], k: int) -> float:
    """Reciprocal rank of the first relevant item within the top k."""
    relevant_ids = _relevant_ids(relevant)
    for rank, doc_id in enumerate(retrieved[:k]):
        if doc_id in relevant_ids:
            return 1.0 / (rank + 1)
    return 0.0


def overlap_recall(approximate: Sequence[str], exact: Sequence[str], k: int) -> float:
    """ANN recall: share of the exact top-k neighbours the approximate search also returned."""
    truth = set(exact[:k])
    return len(truth.intersection(approximate[:k])) / len(truth) if truth else 0.0


def percentile(values: Sequence[float], pct: float) -> float:
    """Linear-interpolated percentile (same method as numpy's default)."""
    if not values:
        return math.nan
    ordered = sorted(values)
    position = (len(ordered) - 1) * pct / 100
    lower = math.floor(position)
    upper = math.ceil(position)
    if lower == upper:
        return ordered[lower]
    return ordered[lower] + (ordered[upper] - ordered[lower]) * (position - lower)


def mean(values: Sequence[float]) -> float:
    return sum(values) / len(values) if values else math.nan


def dedupe_preserving_order(ids: Sequence[str]) -> list[str]:
    """Chunk-level results → document-level ranking (first occurrence = best rank)."""
    seen: set[str] = set()
    ordered = []
    for doc_id in ids:
        if doc_id not in seen:
            seen.add(doc_id)
            ordered.append(doc_id)
    return ordered


def _relevant_ids(relevant: Mapping[str, int] | set[str]) -> set[str]:
    if isinstance(relevant, Mapping):
        return {doc_id for doc_id, grade in relevant.items() if grade > 0}
    return set(relevant)
