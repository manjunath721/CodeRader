"""
"What if?" simulation engine — risk-model.md §5, master spec §18-20.

Operates on a plain in-memory ProjectSnapshot so it can be unit tested
without a database, and reuses the *exact* same scoring/risk functions as
the main analysis pipeline (never a separate, divergent code path).
"""
from dataclasses import dataclass, field

from app.graph.dependency_graph import build_dependency_graph, dependency_concentration_hhi, propagate_risk
from app.risk.hidden_experts import ExpertSignal, rank_backup_candidates
from app.risk.knowledge import bus_factor, knowledge_concentration_hhi
from app.risk.risk_engine import (
    ModuleRiskInput,
    ResilienceInput,
    compute_module_risks,
    compute_resilience_score,
)


@dataclass
class ModuleFacts:
    module_id: str
    name: str
    documentation_score: float
    complexity_avg: float
    change_frequency_90d: int


@dataclass
class ProjectSnapshot:
    modules: list[ModuleFacts]
    # knowledge_scores[module_id][developer_id] = score (0-100)
    knowledge_scores: dict[str, dict[str, float]]
    dependency_edges: list[tuple[str, str]]  # (module_id, depends_on_module_id)
    review_counts: dict[str, dict[str, int]] = field(default_factory=dict)  # [module_id][dev_id]
    issue_counts: dict[str, dict[str, int]] = field(default_factory=dict)


def _project_resilience(snapshot: ProjectSnapshot) -> tuple[float, dict[str, "object"], dict]:
    dep_graph = build_dependency_graph(snapshot.dependency_edges)
    centrality = {n: dep_graph.in_degree(n) + dep_graph.out_degree(n) for n in dep_graph.nodes}

    risk_inputs = []
    concentration_by_module = {}
    bus_factor_by_module = {}
    for m in snapshot.modules:
        scores = snapshot.knowledge_scores.get(m.module_id, {})
        concentration = knowledge_concentration_hhi(list(scores.values())) if scores else 0.0
        bf = bus_factor(scores) if scores else 0
        concentration_by_module[m.module_id] = concentration
        bus_factor_by_module[m.module_id] = bf
        risk_inputs.append(
            ModuleRiskInput(
                module_id=m.module_id,
                concentration_pct=concentration,
                bus_factor=bf,
                documentation_score=m.documentation_score,
                complexity_avg=m.complexity_avg,
                change_frequency_90d=m.change_frequency_90d,
                dependency_centrality=float(centrality.get(m.module_id, 0)),
            )
        )
    risk_results = {r.module_id: r for r in compute_module_risks(risk_inputs)}

    avg_bus_factor = sum(bus_factor_by_module.values()) / len(bus_factor_by_module) if bus_factor_by_module else 0
    max_bf = max(bus_factor_by_module.values(), default=1) or 1
    avg_bus_factor_norm = avg_bus_factor / max_bf if max_bf else 0.0
    avg_concentration = (
        sum(concentration_by_module.values()) / len(concentration_by_module) if concentration_by_module else 0
    )
    avg_doc = (
        sum(m.documentation_score for m in snapshot.modules) / len(snapshot.modules) if snapshot.modules else 0
    )
    critical_risks = [r.score for r in risk_results.values() if r.level in ("HIGH", "CRITICAL")]
    avg_critical_risk = sum(critical_risks) / len(critical_risks) if critical_risks else 0.0
    dep_concentration = dependency_concentration_hhi(dep_graph)

    resilience_score, label, breakdown = compute_resilience_score(
        ResilienceInput(
            avg_bus_factor_norm=avg_bus_factor_norm,
            avg_knowledge_distribution=1 - (avg_concentration / 100),
            avg_documentation_coverage=avg_doc,
            avg_critical_module_risk=avg_critical_risk,
            dependency_concentration=dep_concentration,
        )
    )
    return resilience_score, risk_results, {"label": label, "breakdown": breakdown}


@dataclass
class SimulationOutcome:
    resilience_before: float
    resilience_after: float
    knowledge_impact_pct: float
    affected_modules: list[str]
    risk_before: dict
    risk_after: dict
    risk_propagation: dict[str, dict[str, float]]  # module_id -> {affected_module_id: impact}
    backup_candidates: dict[str, list[dict]]  # module_id -> ranked candidates
    resilience_label_before: str
    resilience_label_after: str


def simulate_unavailability(snapshot: ProjectSnapshot, developer_ids: list[str]) -> SimulationOutcome:
    resilience_before, risk_before, meta_before = _project_resilience(snapshot)

    total_knowledge = sum(
        score for module_scores in snapshot.knowledge_scores.values() for score in module_scores.values()
    )
    removed_knowledge = sum(
        score
        for module_scores in snapshot.knowledge_scores.values()
        for dev_id, score in module_scores.items()
        if dev_id in developer_ids
    )
    knowledge_impact_pct = round(100 * removed_knowledge / total_knowledge, 2) if total_knowledge else 0.0

    affected_modules = [
        m.module_id
        for m in snapshot.modules
        if any(dev_id in snapshot.knowledge_scores.get(m.module_id, {}) for dev_id in developer_ids)
    ]

    reduced_scores = {
        module_id: {dev_id: s for dev_id, s in devs.items() if dev_id not in developer_ids}
        for module_id, devs in snapshot.knowledge_scores.items()
    }
    reduced_snapshot = ProjectSnapshot(
        modules=snapshot.modules,
        knowledge_scores=reduced_scores,
        dependency_edges=snapshot.dependency_edges,
        review_counts=snapshot.review_counts,
        issue_counts=snapshot.issue_counts,
    )
    resilience_after, risk_after, meta_after = _project_resilience(reduced_snapshot)

    dep_graph = build_dependency_graph(snapshot.dependency_edges)
    propagation = {m: propagate_risk(dep_graph, m) for m in affected_modules}

    backup_candidates = {}
    for m in affected_modules:
        remaining = reduced_scores.get(m, {})
        signals = [
            ExpertSignal(
                developer_id=dev_id,
                reviews_count=snapshot.review_counts.get(m, {}).get(dev_id, 0),
                issues_count=snapshot.issue_counts.get(m, {}).get(dev_id, 0),
                related_module_knowledge=0.0,
                technology_overlap=0.0,
            )
            for dev_id in remaining
        ]
        ranked = rank_backup_candidates(
            signals,
            knowledge_scores=remaining,
            recency_scores={d: 0.5 for d in remaining},
            primary_developer_id=None,
        )
        backup_candidates[m] = [
            {"developer_id": r.developer_id, "compatibility": r.compatibility, "reason": r.reason} for r in ranked
        ]

    return SimulationOutcome(
        resilience_before=resilience_before,
        resilience_after=resilience_after,
        knowledge_impact_pct=knowledge_impact_pct,
        affected_modules=affected_modules,
        risk_before={k: v.score for k, v in risk_before.items()},
        risk_after={k: v.score for k, v in risk_after.items()},
        risk_propagation=propagation,
        backup_candidates=backup_candidates,
        resilience_label_before=meta_before["label"],
        resilience_label_after=meta_after["label"],
    )
