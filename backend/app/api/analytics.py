import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.analyzers.module_dependency_resolver import extract_external_libraries
from app.graph.knowledge_graph import build_knowledge_graph, serialize_for_frontend
from app.models.analysis import KnowledgeScore, ResilienceScore, RiskScore
from app.models.code import File, Module, ModuleDependency
from app.models.developer import Developer
from app.models.project import Repository
from app.schemas.analytics import DashboardOut, RecommendationOut
from app.services.query_service import (
    build_dashboard,
    build_recommendations,
    get_latest_complete_run,
    get_project_or_404,
)

router = APIRouter(tags=["analytics"])


@router.get("/projects/{project_id}/dashboard", response_model=DashboardOut)
def get_dashboard(project_id: uuid.UUID, db: Session = Depends(get_db)):
    project = get_project_or_404(db, project_id)
    return build_dashboard(db, project)


@router.get("/projects/{project_id}/developers")
def list_developers(project_id: uuid.UUID, db: Session = Depends(get_db)):
    project = get_project_or_404(db, project_id)
    devs = db.query(Developer).filter(Developer.project_id == project.id).all()
    return [{"id": d.id, "display_name": d.display_name, "primary_email": d.primary_email} for d in devs]


@router.get("/projects/{project_id}/modules")
def list_modules(project_id: uuid.UUID, db: Session = Depends(get_db)):
    project = get_project_or_404(db, project_id)
    repo_ids = [r.id for r in db.query(Repository).filter(Repository.project_id == project.id)]
    modules = db.query(Module).filter(Module.repository_id.in_(repo_ids)).all()
    run = get_latest_complete_run(db, project.id)
    risk_rows = {r.module_id: r for r in db.query(RiskScore).filter(RiskScore.analysis_run_id == run.id)} if run else {}
    out = []
    for m in modules:
        rr = risk_rows.get(m.id)
        out.append(
            {
                "id": m.id, "name": m.name, "path_prefix": m.path_prefix,
                "risk_score": rr.score if rr else None, "risk_level": rr.level if rr else None,
                "bus_factor": rr.bus_factor if rr else None,
                "concentration_pct": rr.concentration_pct if rr else None,
                "is_critical_knowledge_area": rr.is_critical_knowledge_area if rr else False,
            }
        )
    return out


@router.get("/projects/{project_id}/files")
def list_files(project_id: uuid.UUID, limit: int = 150, db: Session = Depends(get_db)):
    """Real per-file inventory (path, language, size, complexity, doc
    coverage) powering the Knowledge Cosmos file layer. Ordered by complexity
    so the most significant files surface first; capped for performance."""
    project = get_project_or_404(db, project_id)
    repo_ids = [r.id for r in db.query(Repository).filter(Repository.project_id == project.id)]
    modules = {m.id: m for m in db.query(Module).filter(Module.repository_id.in_(repo_ids)).all()}
    rows = (
        db.query(File)
        .filter(File.repository_id.in_(repo_ids))
        .order_by(File.complexity.desc(), File.size_bytes.desc())
        .limit(max(1, min(limit, 500)))
        .all()
    )
    return [
        {
            "id": f.id, "path": f.path, "name": f.path.rsplit("/", 1)[-1],
            "language": f.language, "size_bytes": f.size_bytes,
            "complexity": f.complexity, "doc_coverage_pct": f.doc_coverage_pct,
            "is_test": f.is_test, "is_config": f.is_config,
            "module_id": f.module_id,
            "module_name": modules[f.module_id].name if f.module_id in modules else None,
        }
        for f in rows
    ]


@router.get("/projects/{project_id}/libraries")
def list_libraries(project_id: uuid.UUID, db: Session = Depends(get_db)):
    """Genuinely-third-party packages derived from captured source imports
    (anything that does not resolve to an internal module). No invented data:
    empty when analyzers captured no external imports."""
    project = get_project_or_404(db, project_id)
    repo_ids = [r.id for r in db.query(Repository).filter(Repository.project_id == project.id)]
    modules = db.query(Module).filter(Module.repository_id.in_(repo_ids)).all()
    prefixes = [m.path_prefix for m in modules]
    prefix_by_id = {m.id: m.path_prefix for m in modules}
    by_prefix = {m.path_prefix: m.name for m in modules}
    files = db.query(File).filter(File.repository_id.in_(repo_ids)).all()
    libs = extract_external_libraries(
        prefixes,
        [(f.path, prefix_by_id.get(f.module_id, ""), f.import_targets or []) for f in files],
    )
    return [
        {
            "name": lib.name, "file_count": lib.file_count,
            "used_by_modules": [by_prefix[p] for p in lib.used_by_modules if p in by_prefix],
        }
        for lib in libs
    ]


@router.get("/projects/{project_id}/knowledge-graph")
def get_knowledge_graph(
    project_id: uuid.UUID,
    developer_id: uuid.UUID | None = None,
    module_id: uuid.UUID | None = None,
    db: Session = Depends(get_db),
):
    project = get_project_or_404(db, project_id)
    repo_ids = [r.id for r in db.query(Repository).filter(Repository.project_id == project.id)]
    modules = db.query(Module).filter(Module.repository_id.in_(repo_ids)).all()
    devs = db.query(Developer).filter(Developer.project_id == project.id).all()
    run = get_latest_complete_run(db, project.id)
    knowledge_rows = db.query(KnowledgeScore).filter(KnowledgeScore.analysis_run_id == run.id).all() if run else []
    deps = db.query(ModuleDependency).filter(ModuleDependency.module_id.in_([m.id for m in modules])).all()

    g = build_knowledge_graph(
        developers=[{"id": str(d.id), "name": d.display_name} for d in devs],
        modules=[{"id": str(m.id), "name": m.name} for m in modules],
        knowledge_edges=[{"developer_id": str(k.developer_id), "module_id": str(k.module_id), "score": k.score} for k in knowledge_rows],
        dependency_edges=[(str(d.module_id), str(d.depends_on_module_id)) for d in deps],
    )
    return serialize_for_frontend(
        g, developer_filter=str(developer_id) if developer_id else None, module_filter=str(module_id) if module_id else None
    )


@router.get("/projects/{project_id}/risks")
def get_risks(project_id: uuid.UUID, db: Session = Depends(get_db)):
    project = get_project_or_404(db, project_id)
    run = get_latest_complete_run(db, project.id)
    if not run:
        return []
    repo_ids = [r.id for r in db.query(Repository).filter(Repository.project_id == project.id)]
    module_names = {m.id: m.name for m in db.query(Module).filter(Module.repository_id.in_(repo_ids))}
    rows = db.query(RiskScore).filter(RiskScore.analysis_run_id == run.id).all()
    return [
        {
            "module_id": r.module_id, "module_name": module_names.get(r.module_id, "Unknown"),
            "score": r.score, "level": r.level, "factors": r.factors,
            "criticality_score": r.criticality_score, "is_critical_knowledge_area": r.is_critical_knowledge_area,
            "bus_factor": r.bus_factor, "concentration_pct": r.concentration_pct,
        }
        for r in rows
    ]


@router.get("/projects/{project_id}/resilience")
def get_resilience(project_id: uuid.UUID, db: Session = Depends(get_db)):
    project = get_project_or_404(db, project_id)
    run = get_latest_complete_run(db, project.id)
    if not run:
        return {"score": None, "label": None, "component_breakdown": None}
    r = db.query(ResilienceScore).filter(ResilienceScore.analysis_run_id == run.id).first()
    if not r:
        return {"score": None, "label": None, "component_breakdown": None}
    return {"score": r.score, "label": r.label, "component_breakdown": r.component_breakdown}


@router.get("/projects/{project_id}/recommendations", response_model=list[RecommendationOut])
def get_recommendations(project_id: uuid.UUID, db: Session = Depends(get_db)):
    project = get_project_or_404(db, project_id)
    return build_recommendations(db, project)
