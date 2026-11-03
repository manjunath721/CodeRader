"""
Risk & resilience engine — implements docs/risk-model.md §1-3.
Pure functions operating on already-aggregated per-module facts, so they're
easy to unit test independently of the database.
"""
from dataclasses import dataclass

from app.models.project import DEFAULT_RISK_CONFIG


def _normalize_minmax(values: dict[str, float]) -> dict[str, float]:
    if not values:
        return {}
    lo, hi = min(values.values()), max(values.values())
    if hi == lo:
        return {k: 0.0 for k in values}
    return {k: (v - lo) / (hi - lo) for k, v in values.items()}


def risk_level(score: float) -> str:
    if score >= 75:
        return "CRITICAL"
    if score >= 50:
        return "HIGH"
    if score >= 25:
        return "MODERATE"
    return "LOW"


def resilience_label(score: float) -> str:
    if score >= 80:
        return "GOOD"
    if score >= 60:
        return "MODERATE"
    if score >= 35:
        return "AT_RISK"
    return "CRITICAL"


@dataclass
class ModuleRiskInput:
    module_id: str
    concentration_pct: float  # 0-100, from knowledge_concentration_hhi
    bus_factor: int
    documentation_score: float  # 0-1
    complexity_avg: float  # raw avg cyclomatic complexity
    change_frequency_90d: int  # raw commit count in trailing 90d
    dependency_centrality: float  # raw in+out degree in module dependency graph


@dataclass
class ModuleRiskResult:
    module_id: str
    score: float
    level: str
    factors: dict


def compute_module_risks(
    inputs: list[ModuleRiskInput], weights: dict | None = None
) -> list[ModuleRiskResult]:
    weights = weights or DEFAULT_RISK_CONFIG["risk_weights"]
    if not inputs:
        return []

    complexity_norm = _normalize_minmax({i.module_id: i.complexity_avg for i in inputs})
    change_freq_norm = _normalize_minmax({i.module_id: float(i.change_frequency_90d) for i in inputs})
    dependency_norm = _normalize_minmax({i.module_id: i.dependency_centrality for i in inputs})

    results = []
    for inp in inputs:
        factor_values = {
            "knowledge_concentration": inp.concentration_pct / 100,
            "bus_factor_risk": 1 / (1 + inp.bus_factor),
            "documentation_risk": 1 - inp.documentation_score,
            "complexity_risk": complexity_norm.get(inp.module_id, 0.0),
            "change_frequency_risk": change_freq_norm.get(inp.module_id, 0.0),
            "dependency_risk": dependency_norm.get(inp.module_id, 0.0),
        }
        score = round(100 * sum(weights[k] * v for k, v in factor_values.items()), 2)
        results.append(
            ModuleRiskResult(
                module_id=inp.module_id,
                score=score,
                level=risk_level(score),
                factors={
                    "values": {k: round(v, 4) for k, v in factor_values.items()},
                    "weights": weights,
                    "raw": {
                        "concentration_pct": inp.concentration_pct,
                        "bus_factor": inp.bus_factor,
                        "documentation_score": inp.documentation_score,
                        "complexity_avg": inp.complexity_avg,
                        "change_frequency_90d": inp.change_frequency_90d,
                        "dependency_centrality": inp.dependency_centrality,
                    },
                },
            )
        )
    return results


def compute_criticality(
    risk_score: float, dependency_centrality_norm: float, change_frequency_norm: float, loc_share: float,
    threshold: float | None = None,
) -> tuple[float, bool]:
    """docs/risk-model.md §2."""
    threshold = threshold if threshold is not None else DEFAULT_RISK_CONFIG["criticality_threshold"]
    structural_importance = 0.5 * dependency_centrality_norm + 0.3 * change_frequency_norm + 0.2 * loc_share
    criticality = round(risk_score * structural_importance, 2)
    return criticality, criticality >= threshold


@dataclass
class ResilienceInput:
    avg_bus_factor_norm: float  # 0-1, normalized average bus factor across modules
    avg_knowledge_distribution: float  # 0-1, 1 - avg concentration_pct/100
    avg_documentation_coverage: float  # 0-1
    avg_critical_module_risk: float  # 0-100
    dependency_concentration: float  # 0-1, HHI of module dependency graph normalized


def compute_resilience_score(inp: ResilienceInput) -> tuple[float, str, dict]:
    """docs/risk-model.md §3."""
    components = {
        "developer_redundancy": inp.avg_bus_factor_norm,
        "knowledge_distribution": inp.avg_knowledge_distribution,
        "documentation_coverage": inp.avg_documentation_coverage,
        "critical_module_safety": 1 - (inp.avg_critical_module_risk / 100),
        "dependency_decentralization": 1 - inp.dependency_concentration,
    }
    weights = {
        "developer_redundancy": 0.25,
        "knowledge_distribution": 0.20,
        "documentation_coverage": 0.20,
        "critical_module_safety": 0.20,
        "dependency_decentralization": 0.15,
    }
    score = round(100 * sum(weights[k] * v for k, v in components.items()), 2)
    return score, resilience_label(score), {"components": components, "weights": weights}
