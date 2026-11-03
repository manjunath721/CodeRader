import uuid
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.core.errors import CodeResilienceError
from app.models.analysis import KnowledgeScore
from app.models.code import Module, ModuleDependency
from app.models.developer import Developer
from app.models.project import Project, Repository
from app.models.simulation import Simulation, SimulationResult
from app.services.query_service import NoAnalysisRunError, get_latest_complete_run
from app.simulation.engine import ModuleFacts, ProjectSnapshot, simulate_unavailability


class InvalidSimulationRequestError(CodeResilienceError):
    code = "INVALID_SIMULATION_REQUEST"
    status_code = 400
    message = "Provide developer_id or developer_ids."


def run_simulation(db: Session, project: Project, developer_ids: list[uuid.UUID]) -> dict:
    if not developer_ids:
        raise InvalidSimulationRequestError()
    run = get_latest_complete_run(db, project.id)
    if not run:
        raise NoAnalysisRunError()

    repo_ids = [r.id for r in db.query(Repository).filter(Repository.project_id == project.id)]
    modules = db.query(Module).filter(Module.repository_id.in_(repo_ids)).all()
    module_facts = [
        ModuleFacts(
            module_id=str(m.id), name=m.name, documentation_score=m.documentation_score,
            complexity_avg=m.complexity_avg, change_frequency_90d=m.change_frequency_90d,
        )
        for m in modules
    ]
    knowledge_rows = db.query(KnowledgeScore).filter(KnowledgeScore.analysis_run_id == run.id).all()
    knowledge_scores: dict[str, dict[str, float]] = {}
    for k in knowledge_rows:
        knowledge_scores.setdefault(str(k.module_id), {})[str(k.developer_id)] = k.score

    deps = db.query(ModuleDependency).filter(ModuleDependency.module_id.in_([m.id for m in modules])).all()
    dependency_edges = [(str(d.module_id), str(d.depends_on_module_id)) for d in deps]

    snapshot = ProjectSnapshot(
        modules=module_facts, knowledge_scores=knowledge_scores, dependency_edges=dependency_edges,
    )
    outcome = simulate_unavailability(snapshot, [str(d) for d in developer_ids])

    dev_names = {d.id: d.display_name for d in db.query(Developer).filter(Developer.project_id == project.id)}
    module_names = {m.id: m.name for m in modules}

    def name_for_module(mid: str) -> str:
        try:
            return module_names.get(uuid.UUID(mid), mid)
        except ValueError:
            return mid

    def name_for_dev(did: str) -> str:
        try:
            return dev_names.get(uuid.UUID(did), did)
        except ValueError:
            return did

    sim = Simulation(
        project_id=project.id,
        type="single" if len(developer_ids) == 1 else "multiple",
        developer_ids=[str(d) for d in developer_ids],
        requested_at=datetime.now(timezone.utc),
        status="complete",
    )
    db.add(sim)
    db.flush()

    backup_named = {
        name_for_module(mid): [
            {**c, "developer_name": name_for_dev(c["developer_id"])} for c in candidates
        ]
        for mid, candidates in outcome.backup_candidates.items()
    }

    result = SimulationResult(
        simulation_id=sim.id,
        resilience_before=outcome.resilience_before,
        resilience_after=outcome.resilience_after,
        knowledge_impact_pct=outcome.knowledge_impact_pct,
        affected_modules=[{"id": mid, "name": name_for_module(mid)} for mid in outcome.affected_modules],
        backup_candidates=backup_named,
        risk_propagation=outcome.risk_propagation,
    )
    db.add(result)
    db.commit()

    return {
        "simulation_id": sim.id,
        "resilience_before": outcome.resilience_before,
        "resilience_after": outcome.resilience_after,
        "resilience_label_before": outcome.resilience_label_before,
        "resilience_label_after": outcome.resilience_label_after,
        "knowledge_impact_pct": outcome.knowledge_impact_pct,
        "affected_modules": result.affected_modules,
        "backup_candidates": backup_named,
        "risk_propagation": outcome.risk_propagation,
    }
