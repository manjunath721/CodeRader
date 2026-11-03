"""
AI Project Analyst — master spec §24.
User question -> intent detection -> retrieve CodeRadar metrics ->
structured context -> LLM (or deterministic fallback) -> answer.
"""
import re

from sqlalchemy.orm import Session

from app.ai.provider import generate_answer
from app.models.analysis import KnowledgeScore, ResilienceScore, RiskScore
from app.models.code import Module
from app.models.developer import Developer
from app.models.project import Project, Repository
from app.models.simulation import Recommendation
from app.services.query_service import get_latest_complete_run
from app.services.simulation_service import run_simulation


def _find_module_by_name_fragment(db: Session, project: Project, question: str) -> Module | None:
    repo_ids = [r.id for r in db.query(Repository).filter(Repository.project_id == project.id)]
    modules = db.query(Module).filter(Module.repository_id.in_(repo_ids)).all()
    q_lower = question.lower()
    for m in modules:
        if m.name.lower() in q_lower:
            return m
    return None


def _find_developer_by_name_fragment(db: Session, project: Project, question: str) -> Developer | None:
    devs = db.query(Developer).filter(Developer.project_id == project.id).all()
    q_lower = question.lower()
    for d in devs:
        if d.display_name.lower() in q_lower:
            return d
    return None


def answer_question(db: Session, project: Project, question: str) -> dict:
    q = question.lower()
    run = get_latest_complete_run(db, project.id)
    if not run:
        context = {"type": "no_data"}
        return {"answer": generate_answer(question, context), "context": context}

    # Intent: developer-unavailability simulation ("what if X", "X unavailable", "X leaves")
    dev = _find_developer_by_name_fragment(db, project, question)
    if dev and re.search(r"\b(unavailable|leaves|leave|quit|what if|backup for|replace)\b", q):
        result = run_simulation(db, project, [dev.id])
        context = {"type": "simulation", "developer_name": dev.display_name, "simulation": result}
        return {"answer": generate_answer(question, context), "context": context}

    # Intent: backup candidate for a module
    module = _find_module_by_name_fragment(db, project, question)
    if module and re.search(r"\b(backup|who could|replace|secondary)\b", q):
        from app.services.query_service import build_module_detail

        detail = build_module_detail(db, project, module.id)
        context = {"type": "module_backup", "module": {"name": module.name}, "candidates": detail["backup_candidates"]}
        return {"answer": generate_answer(question, context), "context": context}

    # Intent: why is module X risky / who knows module X
    if module:
        risk = db.query(RiskScore).filter(RiskScore.analysis_run_id == run.id, RiskScore.module_id == module.id).first()
        if risk:
            context = {
                "type": "module_risk",
                "module": {
                    "name": module.name, "score": risk.score, "level": risk.level,
                    "concentration_pct": risk.concentration_pct, "bus_factor": risk.bus_factor,
                    "documentation_score": module.documentation_score,
                },
            }
            return {"answer": generate_answer(question, context), "context": context}

    # Intent: overall project resilience
    if re.search(r"\b(resilience|overall risk|how (is|are) (we|the project))\b", q):
        resilience = db.query(ResilienceScore).filter(ResilienceScore.analysis_run_id == run.id).first()
        if resilience:
            context = {
                "type": "resilience",
                "resilience": {"score": resilience.score, "label": resilience.label, "breakdown": resilience.component_breakdown},
            }
            return {"answer": generate_answer(question, context), "context": context}

    # Intent: top risks / recommendations
    if re.search(r"\b(top risk|recommend|what should|document first)\b", q):
        recs = db.query(Recommendation).filter(Recommendation.analysis_run_id == run.id).all()
        context = {
            "type": "recommendations",
            "recommendations": [{"severity": r.severity, "title": r.title, "description": r.description} for r in recs],
        }
        return {"answer": generate_answer(question, context), "context": context}

    context = {"type": "no_data"}
    return {"answer": generate_answer(question, context), "context": context}
