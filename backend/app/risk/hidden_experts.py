"""
Hidden-expert detection and backup-candidate ranking — methodology.md §7-8.
"""
from dataclasses import dataclass


def _normalize_minmax(values: dict) -> dict:
    if not values:
        return {}
    lo, hi = min(values.values()), max(values.values())
    if hi == lo:
        return {k: (1.0 if hi > 0 else 0.0) for k in values}
    return {k: (v - lo) / (hi - lo) for k, v in values.items()}


@dataclass
class ExpertSignal:
    developer_id: str
    reviews_count: int = 0
    issues_count: int = 0
    related_module_knowledge: float = 0.0
    technology_overlap: float = 0.0


@dataclass
class ExpertScore:
    developer_id: str
    score: float
    reason: str


def detect_hidden_experts(signals, primary_developer_id, top_n=3):
    candidates = [s for s in signals if s.developer_id != primary_developer_id]
    if not candidates:
        return []

    review_n = _normalize_minmax({s.developer_id: float(s.reviews_count) for s in candidates})
    issue_n = _normalize_minmax({s.developer_id: float(s.issues_count) for s in candidates})
    related_n = _normalize_minmax({s.developer_id: s.related_module_knowledge for s in candidates})
    tech_n = _normalize_minmax({s.developer_id: s.technology_overlap for s in candidates})

    scored = []
    for s in candidates:
        score = round(
            100 * (
                0.35 * review_n.get(s.developer_id, 0.0)
                + 0.25 * issue_n.get(s.developer_id, 0.0)
                + 0.20 * related_n.get(s.developer_id, 0.0)
                + 0.20 * tech_n.get(s.developer_id, 0.0)
            ),
            2,
        )
        reasons = []
        if s.reviews_count:
            reasons.append(f"{s.reviews_count} code review(s)")
        if s.issues_count:
            reasons.append(f"{s.issues_count} issue(s) resolved")
        if s.related_module_knowledge > 0:
            reasons.append("knowledge in related/dependent modules")
        if s.technology_overlap > 0:
            reasons.append("technology overlap with this module")
        reason = "Surfaced via " + ", ".join(reasons) if reasons else "Limited secondary signal"
        scored.append(ExpertScore(developer_id=s.developer_id, score=score, reason=reason))

    scored.sort(key=lambda e: e.score, reverse=True)
    return scored[:top_n]


@dataclass
class BackupCandidateResult:
    developer_id: str
    compatibility: float
    reason: str


def rank_backup_candidates(signals, knowledge_scores, recency_scores, primary_developer_id, top_n=5):
    candidates = [s for s in signals if s.developer_id != primary_developer_id]
    if not candidates:
        return []

    know_n = _normalize_minmax({s.developer_id: knowledge_scores.get(s.developer_id, 0.0) for s in candidates})
    related_n = _normalize_minmax({s.developer_id: s.related_module_knowledge for s in candidates})
    tech_n = _normalize_minmax({s.developer_id: s.technology_overlap for s in candidates})
    review_n = _normalize_minmax({s.developer_id: float(s.reviews_count) for s in candidates})
    recency_n = _normalize_minmax({s.developer_id: recency_scores.get(s.developer_id, 0.0) for s in candidates})

    results = []
    for s in candidates:
        compatibility = round(
            100 * (
                0.40 * know_n.get(s.developer_id, 0.0)
                + 0.25 * related_n.get(s.developer_id, 0.0)
                + 0.15 * tech_n.get(s.developer_id, 0.0)
                + 0.10 * review_n.get(s.developer_id, 0.0)
                + 0.10 * recency_n.get(s.developer_id, 0.0)
            ),
            2,
        )
        results.append(
            BackupCandidateResult(
                developer_id=s.developer_id,
                compatibility=compatibility,
                reason="Repository-derived backup candidate based on module knowledge, "
                       "related-module experience, technology overlap, reviews, and recent activity.",
            )
        )
    results.sort(key=lambda r: r.compatibility, reverse=True)
    return results[:top_n]
