"""
Read-side query helpers used by the API routers. Keeps routers thin
(architecture.md 2): validate -> call service -> serialize.
"""
import uuid

from sqlalchemy.orm import Session

from app.core.errors import CodeResilienceError
from app.models.activity import DeveloperModuleActivity
from app.models.analysis import AnalysisRun, KnowledgeScore, ResilienceScore, RiskScore
from app.models.code import Module, ModuleDependency
from app.models.developer import Developer
from app.models.project import Project, Repository
from app.models.simulation import Recommendation
from app.risk.hidden_experts import ExpertSignal, rank_backup_candidates


class ProjectNotFoundError(CodeResilienceError):
    code = "PROJECT_NOT_FOUND"
    status_code = 404
    message = "Project not found."


class ModuleNotFoundError(CodeResilienceError):
    code = "MODULE_NOT_FOUND"
    status_code = 404
    message = "Module not found."


class DeveloperNotFoundError(CodeResilienceError):
    code = "DEVELOPER_NOT_FOUND"
    status_code = 404
    message = "Developer not found."


class NoAnalysisRunError(CodeResilienceError):
    code = "NO_ANALYSIS_RUN"
    status_code = 404
    message = "This project has not been analyzed yet. Run analysis first."


def get_project_or_404(db: Session, project_id: uuid.UUID) -> Project:
    project = db.get(Project, project_id)
    if not project:
        raise ProjectNotFoundError()
    return project


def get_latest_complete_run(db: Session, project_id: uuid.UUID) -> AnalysisRun | None:
    return (
        db.query(AnalysisRun)
        .filter(AnalysisRun.project_id == project_id, AnalysisRun.status == "complete")
        .order_by(AnalysisRun.completed_at.desc())
        .first()
    )


def _module_repo_ids(db: Session, project_id: uuid.UUID) -> list:
    return [r.id for r in db.query(Repository).filter(Repository.project_id == project_id)]


def build_dashboard(db: Session, project: Project) -> dict:
    run = get_latest_complete_run(db, project.id)
    modules = db.query(Module).filter(Module.repository_id.in_(_module_repo_ids(db, project.id))).all()
    developer_count = db.query(Developer).filter(Developer.project_id == project.id).count()

    if not run:
        return {
            "project_id": project.id,
            "project_name": project.name,
            "is_demo": project.is_demo,
            "resilience_score": None,
            "resilience_label": None,
            "risk_distribution": {"LOW": 0, "MODERATE": 0, "HIGH": 0, "CRITICAL": 0},
            "top_risk_modules": [],
            "critical_knowledge_areas": [],
            "developer_count": developer_count,
            "module_count": len(modules),
            "last_analysis_run_id": None,
            "last_analyzed_at": None,
        }

    risk_rows = {r.module_id: r for r in db.query(RiskScore).filter(RiskScore.analysis_run_id == run.id)}
    resilience = db.query(ResilienceScore).filter(ResilienceScore.analysis_run_id == run.id).first()

    distribution = {"LOW": 0, "MODERATE": 0, "HIGH": 0, "CRITICAL": 0}
    module_summaries = []
    critical_areas = []
    for m in modules:
        rr = risk_rows.get(m.id)
        if not rr:
            continue
        distribution[rr.level] = distribution.get(rr.level, 0) + 1
        summary = {
            "id": m.id, "name": m.name, "risk_score": rr.score, "risk_level": rr.level,
            "bus_factor": rr.bus_factor, "concentration_pct": rr.concentration_pct,
            "is_critical_knowledge_area": rr.is_critical_knowledge_area,
        }
        module_summaries.append(summary)
        if rr.is_critical_knowledge_area:
            critical_areas.append(summary)

    module_summaries.sort(key=lambda s: s["risk_score"] or 0, reverse=True)

    return {
        "project_id": project.id,
        "project_name": project.name,
        "is_demo": project.is_demo,
        "resilience_score": resilience.score if resilience else None,
        "resilience_label": resilience.label if resilience else None,
        "risk_distribution": distribution,
        "top_risk_modules": module_summaries[:5],
        "critical_knowledge_areas": critical_areas,
        "developer_count": developer_count,
        "module_count": len(modules),
        "last_analysis_run_id": run.id,
        "last_analyzed_at": run.completed_at.isoformat() if run.completed_at else None,
    }


def build_module_detail(db: Session, project: Project, module_id: uuid.UUID) -> dict:
    module = db.get(Module, module_id)
    if not module or module.repository_id not in _module_repo_ids(db, project.id):
        raise ModuleNotFoundError()
    run = get_latest_complete_run(db, project.id)
    if not run:
        raise NoAnalysisRunError()

    risk = db.query(RiskScore).filter(RiskScore.analysis_run_id == run.id, RiskScore.module_id == module.id).first()
    knowledge_rows = (
        db.query(KnowledgeScore)
        .filter(KnowledgeScore.analysis_run_id == run.id, KnowledgeScore.module_id == module.id)
        .all()
    )
    dev_names = {d.id: d.display_name for d in db.query(Developer).filter(Developer.project_id == project.id)}
    distribution = sorted(
        [
            {"developer_id": k.developer_id, "developer_name": dev_names.get(k.developer_id, "Unknown"), "score": k.score}
            for k in knowledge_rows
        ],
        key=lambda x: x["score"], reverse=True,
    )

    scores_by_dev = {k.developer_id: k.score for k in knowledge_rows}
    primary = max(scores_by_dev, key=scores_by_dev.get) if scores_by_dev else None
    activity_rows = (
        db.query(DeveloperModuleActivity).filter(DeveloperModuleActivity.module_id == module.id).all()
    )
    signals = [
        ExpertSignal(developer_id=a.developer_id, reviews_count=a.reviews_count, issues_count=a.issues_count)
        for a in activity_rows
    ]
    backups = rank_backup_candidates(
        signals, knowledge_scores=scores_by_dev, recency_scores={a.developer_id: 0.5 for a in activity_rows},
        primary_developer_id=primary,
    )
    backup_out = [
        {"developer_id": b.developer_id, "developer_name": dev_names.get(b.developer_id, "Unknown"),
         "compatibility": b.compatibility, "reason": b.reason}
        for b in backups
    ]

    deps = db.query(ModuleDependency).filter(ModuleDependency.module_id == module.id).all()
    dependents = db.query(ModuleDependency).filter(ModuleDependency.depends_on_module_id == module.id).all()

    return {
        "id": module.id, "name": module.name, "path_prefix": module.path_prefix,
        "risk_score": risk.score if risk else None, "risk_level": risk.level if risk else None,
        "risk_factors": risk.factors if risk else None,
        "bus_factor": risk.bus_factor if risk else None,
        "concentration_pct": risk.concentration_pct if risk else None,
        "documentation_score": module.documentation_score, "complexity_avg": module.complexity_avg,
        "change_frequency_90d": module.change_frequency_90d,
        "is_critical_knowledge_area": risk.is_critical_knowledge_area if risk else False,
        "knowledge_distribution": distribution,
        "backup_candidates": backup_out,
        "dependencies": [str(d.depends_on_module_id) for d in deps],
        "dependents": [str(d.module_id) for d in dependents],
    }


def build_developer_detail(db: Session, project: Project, developer_id: uuid.UUID) -> dict:
    dev = db.get(Developer, developer_id)
    if not dev or dev.project_id != project.id:
        raise DeveloperNotFoundError()
    run = get_latest_complete_run(db, project.id)
    knowledge_rows = (
        db.query(KnowledgeScore).filter(
            KnowledgeScore.developer_id == dev.id, KnowledgeScore.analysis_run_id == run.id
        ).all()
        if run else []
    )
    modules = {m.id: m for m in db.query(Module).filter(Module.repository_id.in_(_module_repo_ids(db, project.id)))}
    module_list = [
        {
            "module_id": k.module_id,
            "module_name": modules[k.module_id].name if k.module_id in modules else "Unknown",
            "score": k.score,
        }
        for k in knowledge_rows
    ]

    critical_ownership = 0
    single_owner = 0
    if run:
        risk_rows = {r.module_id: r for r in db.query(RiskScore).filter(RiskScore.analysis_run_id == run.id)}
        for k in knowledge_rows:
            module_scores = [
                ks.score for ks in db.query(KnowledgeScore).filter(
                    KnowledgeScore.analysis_run_id == run.id, KnowledgeScore.module_id == k.module_id
                )
            ]
            is_primary = k.score == max(module_scores) if module_scores else False
            rr = risk_rows.get(k.module_id)
            if is_primary and rr and rr.is_critical_knowledge_area:
                critical_ownership += 1
            if is_primary and rr and rr.bus_factor <= 1:
                single_owner += 1

    dependency_risk = "HIGH" if single_owner >= 2 else "MODERATE" if single_owner == 1 else "LOW"

    return {
        "id": dev.id, "display_name": dev.display_name, "primary_email": dev.primary_email,
        "modules": module_list, "critical_ownership_count": critical_ownership,
        "single_owner_modules_count": single_owner, "dependency_risk": dependency_risk,
    }


def build_recommendations(db: Session, project: Project) -> list:
    run = get_latest_complete_run(db, project.id)
    if not run:
        return []
    return db.query(Recommendation).filter(Recommendation.analysis_run_id == run.id).all()
