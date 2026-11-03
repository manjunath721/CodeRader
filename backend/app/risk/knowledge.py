"""
Knowledge scoring engine — implements docs/analysis-methodology.md §3.

knowledge_score(d, m) = 100 * normalize(
    w1*contribution + w2*recency + w3*module_experience + w4*review + w5*issue
)
All five components are min-max normalized to [0,1] *within that module*
across its contributors before weighting.
"""
import math
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timezone

from app.models.project import DEFAULT_RISK_CONFIG


@dataclass
class ModuleActivity:
    commits_count: int = 0
    lines_changed: int = 0
    last_commit_at: datetime | None = None
    reviews_count: int = 0
    issues_count: int = 0


@dataclass
class KnowledgeResult:
    developer_id: str
    module_id: str
    score: float
    components: dict


def _minmax_normalize(values: dict[str, float]) -> dict[str, float]:
    if not values:
        return {}
    lo, hi = min(values.values()), max(values.values())
    if hi == lo:
        # All equal (including the single-contributor case) -> everyone gets full credit.
        return {k: 1.0 for k in values}
    return {k: (v - lo) / (hi - lo) for k, v in values.items()}


def compute_module_knowledge_scores(
    module_id: str,
    activity_by_developer: dict[str, ModuleActivity],
    now: datetime | None = None,
    weights: dict | None = None,
    half_life_days: int | None = None,
) -> list[KnowledgeResult]:
    """
    activity_by_developer: developer_id -> ModuleActivity for this one module.
    Returns one KnowledgeResult per developer with contributions to this module.
    """
    now = now or datetime.now(timezone.utc)
    weights = weights or DEFAULT_RISK_CONFIG["knowledge_weights"]
    half_life = half_life_days or DEFAULT_RISK_CONFIG["recency_half_life_days"]
    decay_lambda = math.log(2) / half_life

    if not activity_by_developer:
        return []

    contribution_raw = {d: math.log1p(a.lines_changed) for d, a in activity_by_developer.items()}
    recency_raw = {
        d: math.exp(-decay_lambda * max((now - a.last_commit_at).days, 0)) if a.last_commit_at else 0.0
        for d, a in activity_by_developer.items()
    }
    experience_raw = {d: float(a.commits_count) for d, a in activity_by_developer.items()}
    review_raw = {d: float(a.reviews_count) for d, a in activity_by_developer.items()}
    issue_raw = {d: float(a.issues_count) for d, a in activity_by_developer.items()}

    contribution = _minmax_normalize(contribution_raw)
    recency = _minmax_normalize(recency_raw)
    experience = _minmax_normalize(experience_raw)
    review = _minmax_normalize(review_raw)
    issue = _minmax_normalize(issue_raw)

    results = []
    for dev_id in activity_by_developer:
        combined = (
            weights["contribution"] * contribution.get(dev_id, 0.0)
            + weights["recency"] * recency.get(dev_id, 0.0)
            + weights["module_experience"] * experience.get(dev_id, 0.0)
            + weights["review"] * review.get(dev_id, 0.0)
            + weights["issue"] * issue.get(dev_id, 0.0)
        )
        score = round(100 * combined, 2)
        results.append(
            KnowledgeResult(
                developer_id=dev_id,
                module_id=module_id,
                score=score,
                components={
                    "contribution": round(contribution.get(dev_id, 0.0), 4),
                    "recency": round(recency.get(dev_id, 0.0), 4),
                    "module_experience": round(experience.get(dev_id, 0.0), 4),
                    "review": round(review.get(dev_id, 0.0), 4),
                    "issue": round(issue.get(dev_id, 0.0), 4),
                    "weights": weights,
                },
            )
        )
    return results


def knowledge_concentration_hhi(scores: list[float]) -> float:
    """
    HHI-based concentration (methodology.md §4). Input: raw knowledge scores
    for a module's contributors. Returns concentration_pct on a 0-100 scale.
    """
    total = sum(scores)
    if total <= 0:
        return 0.0
    shares_pct = [100 * s / total for s in scores]
    hhi = sum(s ** 2 for s in shares_pct)  # 0-10000
    return round(hhi / 100, 2)  # normalized to 0-100


def bus_factor(scores_by_developer: dict[str, float], threshold: float | None = None) -> int:
    threshold = threshold if threshold is not None else DEFAULT_RISK_CONFIG["bus_factor_threshold"]
    return sum(1 for s in scores_by_developer.values() if s >= threshold)
