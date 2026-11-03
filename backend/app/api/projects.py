import uuid

from fastapi import APIRouter, BackgroundTasks, Depends
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.errors import CodeResilienceError
from app.models.project import Project, Repository
from app.schemas.project import AnalysisRunOut, ProjectCreate, ProjectOut, RepositoryCreate, RepositoryOut
from app.services.analysis_pipeline import run_analysis
from app.services.project_service import delete_project
from app.services.query_service import get_project_or_404

router = APIRouter(tags=["projects"])


class AnalysisRunNotFoundError(CodeResilienceError):
    code = "ANALYSIS_RUN_NOT_FOUND"
    status_code = 404
    message = "Analysis run not found."


class AnalysisAlreadyRunningError(CodeResilienceError):
    code = "ANALYSIS_ALREADY_RUNNING"
    status_code = 409
    message = "An analysis is already running for this project."


class ProjectDeleteBlockedError(CodeResilienceError):
    code = "PROJECT_DELETE_BLOCKED"
    status_code = 409
    message = "Cannot delete a project while an analysis is running. Cancel it first."


@router.post("/projects", response_model=ProjectOut, status_code=201)
def create_project(payload: ProjectCreate, db: Session = Depends(get_db)):
    project = Project(name=payload.name, description=payload.description)
    db.add(project)
    db.commit()
    db.refresh(project)
    return project


@router.get("/projects", response_model=list[ProjectOut])
def list_projects(db: Session = Depends(get_db)):
    return db.query(Project).order_by(Project.created_at.desc()).all()


@router.get("/projects/{project_id}", response_model=ProjectOut)
def get_project(project_id: uuid.UUID, db: Session = Depends(get_db)):
    return get_project_or_404(db, project_id)


@router.delete("/projects/{project_id}", status_code=204)
def remove_project(project_id: uuid.UUID, db: Session = Depends(get_db)):
    """Deletes a project and all of its repositories, analyses, modules,
    knowledge scores, simulations, and recommendations (FK-safe ordered
    cleanup). Refused with 409 while an analysis run is in progress."""
    from app.models.analysis import AnalysisRun as AnalysisRunModel

    project = get_project_or_404(db, project_id)
    active = (
        db.query(AnalysisRunModel)
        .filter(AnalysisRunModel.project_id == project.id, AnalysisRunModel.status.in_(["pending", "running"]))
        .first()
    )
    if active:
        raise ProjectDeleteBlockedError()
    delete_project(db, project)
    return None


@router.post("/projects/{project_id}/repositories", response_model=RepositoryOut, status_code=201)
def add_repository(project_id: uuid.UUID, payload: RepositoryCreate, db: Session = Depends(get_db)):
    project = get_project_or_404(db, project_id)
    repo = Repository(project_id=project.id, url=payload.url, provider=payload.provider)
    db.add(repo)
    db.commit()
    db.refresh(repo)
    return repo


def _run_analysis_background(project_id: uuid.UUID, run_id: uuid.UUID) -> None:
    # Background tasks get their own DB session (FastAPI BackgroundTasks run
    # after the response but still within this process — see architecture.md
    # §3/§7 for the documented Celery/RQ upgrade path for production scale).
    from app.core.db import SessionLocal
    from app.models.analysis import AnalysisRun

    db = SessionLocal()
    try:
        project = db.get(Project, project_id)
        run = db.get(AnalysisRun, run_id)
        if project and run:
            run_analysis(db, project, run=run)
    finally:
        db.close()


@router.post("/projects/{project_id}/analyze", response_model=AnalysisRunOut, status_code=202)
def start_analysis(
    project_id: uuid.UUID,
    background_tasks: BackgroundTasks,
    scan_mode: str = "full",
    db: Session = Depends(get_db),
):
    project = get_project_or_404(db, project_id)
    from datetime import datetime, timezone

    from app.models.analysis import AnalysisRun

    if scan_mode not in ("quick", "full"):
        scan_mode = "full"

    # Fast-path check for a friendly error without wasting work — NOT the actual
    # safety guarantee (see the race note below).
    existing = (
        db.query(AnalysisRun)
        .filter(AnalysisRun.project_id == project.id, AnalysisRun.status.in_(["pending", "running"]))
        .first()
    )
    if existing:
        raise AnalysisAlreadyRunningError()

    placeholder = AnalysisRun(
        project_id=project.id, status="pending", stage_status={}, scan_mode=scan_mode,
        started_at=datetime.now(timezone.utc),
    )
    db.add(placeholder)
    try:
        # The actual safety guarantee: a partial unique index on
        # (project_id) WHERE status IN ('pending','running') — see migration
        # 9fd52e3c4171. This is what actually stops two concurrent requests
        # from both passing the check above and starting two runs.
        db.commit()
    except IntegrityError:
        db.rollback()
        raise AnalysisAlreadyRunningError()
    db.refresh(placeholder)
    background_tasks.add_task(_run_analysis_background, project.id, placeholder.id)
    return placeholder


@router.post("/projects/{project_id}/analysis-runs/{run_id}/cancel", response_model=AnalysisRunOut)
def cancel_analysis_run(project_id: uuid.UUID, run_id: uuid.UUID, db: Session = Depends(get_db)):
    from app.models.analysis import AnalysisRun

    get_project_or_404(db, project_id)
    run = db.get(AnalysisRun, run_id)
    if not run or run.project_id != project_id:
        raise AnalysisRunNotFoundError()
    if run.status in ("pending", "running"):
        # Cooperative cancellation: the pipeline checks this flag between stages
        # (see analysis_pipeline.run_analysis) and stops cleanly rather than
        # being killed mid-write, so a cancelled run never gets marked complete
        # or leaves partially-computed results published.
        run.cancel_requested = True
        db.add(run)
        db.commit()
        db.refresh(run)
    return run


@router.get("/projects/{project_id}/analysis-runs/{run_id}", response_model=AnalysisRunOut)
def get_analysis_run(project_id: uuid.UUID, run_id: uuid.UUID, db: Session = Depends(get_db)):
    from app.models.analysis import AnalysisRun

    get_project_or_404(db, project_id)
    run = db.get(AnalysisRun, run_id)
    if not run or run.project_id != project_id:
        raise AnalysisRunNotFoundError()
    return run


@router.get("/projects/{project_id}/analysis-runs", response_model=list[AnalysisRunOut])
def list_analysis_runs(project_id: uuid.UUID, db: Session = Depends(get_db)):
    from app.models.analysis import AnalysisRun

    get_project_or_404(db, project_id)
    return (
        db.query(AnalysisRun)
        .filter(AnalysisRun.project_id == project_id)
        .order_by(AnalysisRun.created_at.desc())
        .limit(20)
        .all()
    )
