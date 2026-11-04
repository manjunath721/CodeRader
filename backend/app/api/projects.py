import csv
import io
import json
import uuid
from datetime import datetime, timezone
from typing import Literal

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, Request, Response, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.errors import CodeResilienceError
from app.models.activity import DeveloperModuleActivity
from app.models.analysis import AnalysisRun, KnowledgeScore, ResilienceScore, RiskScore
from app.models.auth import ProjectMember, User
from app.models.code import Module
from app.models.developer import Developer
from app.models.project import DEFAULT_RISK_CONFIG, Project, Repository
from app.models.simulation import Recommendation
from app.schemas.project import (
    AnalysisComparisonOut,
    AnalysisRunOut,
    AnalyzeRequest,
    ProjectCreate,
    ProjectOut,
    ProjectRiskConfigUpdate,
    RepositoryCreate,
    RepositoryOut,
)
from app.services.auth_service import check_project_membership, get_client_ip, get_optional_current_user, log_audit
from app.services.job_worker import enqueue_analysis_job
from app.services.project_service import delete_project
from app.services.query_service import compare_analysis_runs, get_project_or_404

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
def create_project(
    payload: ProjectCreate,
    request: Request,
    user: User | None = Depends(get_optional_current_user),
    db: Session = Depends(get_db),
):
    cfg = dict(DEFAULT_RISK_CONFIG)
    if payload.risk_config:
        cfg.update(payload.risk_config)

    project = Project(
        name=payload.name,
        description=payload.description,
        risk_config=cfg,
    )
    db.add(project)
    db.commit()
    db.refresh(project)

    if user:
        member = ProjectMember(project_id=project.id, user_id=user.id, role="owner")
        db.add(member)
        db.commit()

    ip = get_client_ip(request)
    log_audit(
        db,
        action="PROJECT_CREATED",
        resource_type="project",
        resource_id=str(project.id),
        actor=user,
        details={"name": project.name},
        ip_address=ip,
    )
    return project


@router.get("/projects", response_model=list[ProjectOut])
def list_projects(
    user: User | None = Depends(get_optional_current_user),
    db: Session = Depends(get_db),
):
    if user and user.role != "admin":
        member_proj_ids = [
            m.project_id for m in db.query(ProjectMember.project_id).filter(ProjectMember.user_id == user.id).all()
        ]
        return (
            db.query(Project)
            .filter((Project.id.in_(member_proj_ids)) | (Project.is_demo.is_(True)))
            .order_by(Project.created_at.desc())
            .all()
        )
    return db.query(Project).order_by(Project.created_at.desc()).all()


@router.get("/projects/{project_id}", response_model=ProjectOut)
def get_project(
    project_id: uuid.UUID,
    user: User | None = Depends(get_optional_current_user),
    db: Session = Depends(get_db),
):
    project = get_project_or_404(db, project_id)
    if not check_project_membership(db, project_id, user, min_role="viewer"):
        raise HTTPException(status_code=403, detail="Access denied to this project.")
    return project


@router.delete("/projects/{project_id}", status_code=204)
def remove_project(
    project_id: uuid.UUID,
    request: Request,
    user: User | None = Depends(get_optional_current_user),
    db: Session = Depends(get_db),
):
    project = get_project_or_404(db, project_id)
    if not check_project_membership(db, project_id, user, min_role="owner"):
        raise HTTPException(status_code=403, detail="Only project owners can delete this project.")

    active = (
        db.query(AnalysisRun)
        .filter(AnalysisRun.project_id == project.id, AnalysisRun.status.in_(["pending", "running"]))
        .first()
    )
    if active:
        raise ProjectDeleteBlockedError()

    ip = get_client_ip(request)
    log_audit(
        db,
        action="PROJECT_DELETED",
        resource_type="project",
        resource_id=str(project.id),
        actor=user,
        details={"name": project.name},
        ip_address=ip,
    )
    delete_project(db, project)
    return None


@router.post("/projects/{project_id}/repositories", response_model=RepositoryOut, status_code=201)
def add_repository(
    project_id: uuid.UUID,
    payload: RepositoryCreate,
    request: Request,
    user: User | None = Depends(get_optional_current_user),
    db: Session = Depends(get_db),
):
    project = get_project_or_404(db, project_id)
    if not check_project_membership(db, project_id, user, min_role="owner"):
        raise HTTPException(status_code=403, detail="Only project owners can attach repositories.")

    repo = Repository(project_id=project.id, url=payload.url, provider=payload.provider)
    db.add(repo)
    db.commit()
    db.refresh(repo)

    ip = get_client_ip(request)
    log_audit(
        db,
        action="REPOSITORY_ATTACHED",
        resource_type="repository",
        resource_id=str(repo.id),
        actor=user,
        details={"url": repo.url, "project_id": str(project.id)},
        ip_address=ip,
    )
    return repo


@router.post("/projects/{project_id}/analyze", response_model=AnalysisRunOut, status_code=202)
def start_analysis(
    project_id: uuid.UUID,
    background_tasks: BackgroundTasks,
    request: Request,
    payload: AnalyzeRequest | None = None,
    scan_mode: str | None = Query(default=None),
    rescan_type: str = Query(default="manual"),
    user: User | None = Depends(get_optional_current_user),
    db: Session = Depends(get_db),
):
    project = get_project_or_404(db, project_id)
    if not check_project_membership(db, project_id, user, min_role="analyst"):
        raise HTTPException(status_code=403, detail="Only project analysts or owners can trigger analysis.")

    effective_mode = "full"
    force_full = False
    if payload:
        effective_mode = payload.scan_mode
        force_full = payload.force_full_rescan
    elif scan_mode:
        effective_mode = scan_mode

    if effective_mode not in ("quick", "full", "incremental"):
        effective_mode = "full"

    if effective_mode == "incremental":
        mode_for_pipeline = "full"
    else:
        mode_for_pipeline = effective_mode

    # Concurrency check
    existing = (
        db.query(AnalysisRun)
        .filter(AnalysisRun.project_id == project.id, AnalysisRun.status.in_(["pending", "running"]))
        .first()
    )
    if existing:
        raise AnalysisAlreadyRunningError()

    now = datetime.now(timezone.utc)
    placeholder = AnalysisRun(
        project_id=project.id,
        status="pending",
        stage_status={},
        progress={},
        scan_mode=mode_for_pipeline,
        rescan_type=rescan_type or effective_mode,
        started_at=now,
    )
    db.add(placeholder)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise AnalysisAlreadyRunningError()
    db.refresh(placeholder)

    from app.services.job_worker import _execute_analysis_task
    background_tasks.add_task(_execute_analysis_task, project.id, placeholder.id)

    ip = get_client_ip(request)
    log_audit(
        db,
        action="ANALYSIS_TRIGGERED",
        resource_type="analysis_run",
        resource_id=str(placeholder.id),
        actor=user,
        details={"scan_mode": effective_mode, "rescan_type": rescan_type, "force_full": force_full},
        ip_address=ip,
    )
    return placeholder


@router.post("/projects/{project_id}/analysis-runs/{run_id}/cancel", response_model=AnalysisRunOut)
def cancel_analysis_run(
    project_id: uuid.UUID,
    run_id: uuid.UUID,
    request: Request,
    user: User | None = Depends(get_optional_current_user),
    db: Session = Depends(get_db),
):
    get_project_or_404(db, project_id)
    if not check_project_membership(db, project_id, user, min_role="analyst"):
        raise HTTPException(status_code=403, detail="Permission denied to cancel analysis.")

    run = db.get(AnalysisRun, run_id)
    if not run or run.project_id != project_id:
        raise AnalysisRunNotFoundError()

    if run.status in ("pending", "running"):
        run.cancel_requested = True
        db.add(run)
        db.commit()
        db.refresh(run)

        ip = get_client_ip(request)
        log_audit(
            db,
            action="ANALYSIS_CANCELLED",
            resource_type="analysis_run",
            resource_id=str(run.id),
            actor=user,
            details={"project_id": str(project_id)},
            ip_address=ip,
        )
    return run


@router.get("/projects/{project_id}/analysis-runs/{run_id}", response_model=AnalysisRunOut)
def get_analysis_run(
    project_id: uuid.UUID,
    run_id: uuid.UUID,
    user: User | None = Depends(get_optional_current_user),
    db: Session = Depends(get_db),
):
    get_project_or_404(db, project_id)
    if not check_project_membership(db, project_id, user, min_role="viewer"):
        raise HTTPException(status_code=403, detail="Access denied.")
    run = db.get(AnalysisRun, run_id)
    if not run or run.project_id != project_id:
        raise AnalysisRunNotFoundError()
    return run


@router.get("/projects/{project_id}/analysis-runs", response_model=list[AnalysisRunOut])
def list_analysis_runs(
    project_id: uuid.UUID,
    limit: int = 20,
    user: User | None = Depends(get_optional_current_user),
    db: Session = Depends(get_db),
):
    get_project_or_404(db, project_id)
    if not check_project_membership(db, project_id, user, min_role="viewer"):
        raise HTTPException(status_code=403, detail="Access denied.")
    return (
        db.query(AnalysisRun)
        .filter(AnalysisRun.project_id == project_id)
        .order_by(AnalysisRun.created_at.desc())
        .limit(min(limit, 100))
        .all()
    )


# --- Risk Configuration Endpoints ---
@router.get("/projects/{project_id}/risk-config", response_model=dict)
def get_project_risk_config(
    project_id: uuid.UUID,
    user: User | None = Depends(get_optional_current_user),
    db: Session = Depends(get_db),
):
    project = get_project_or_404(db, project_id)
    if not check_project_membership(db, project_id, user, min_role="viewer"):
        raise HTTPException(status_code=403, detail="Access denied.")
    return project.risk_config or dict(DEFAULT_RISK_CONFIG)


@router.patch("/projects/{project_id}/risk-config", response_model=dict)
def update_project_risk_config(
    project_id: uuid.UUID,
    payload: ProjectRiskConfigUpdate,
    request: Request,
    user: User | None = Depends(get_optional_current_user),
    db: Session = Depends(get_db),
):
    project = get_project_or_404(db, project_id)
    if not check_project_membership(db, project_id, user, min_role="owner"):
        raise HTTPException(status_code=403, detail="Only project owners can modify risk configuration.")

    current_cfg = dict(project.risk_config or DEFAULT_RISK_CONFIG)
    updates = payload.model_dump(exclude_unset=True)

    if "risk_weights" in updates and updates["risk_weights"]:
        current_cfg["risk_weights"] = updates["risk_weights"]
    if "knowledge_weights" in updates and updates["knowledge_weights"]:
        current_cfg["knowledge_weights"] = updates["knowledge_weights"]
    if "bus_factor_threshold" in updates and updates["bus_factor_threshold"] is not None:
        current_cfg["bus_factor_threshold"] = updates["bus_factor_threshold"]
    if "criticality_threshold" in updates and updates["criticality_threshold"] is not None:
        current_cfg["criticality_threshold"] = updates["criticality_threshold"]
    if "propagation_decay" in updates and updates["propagation_decay"] is not None:
        current_cfg["propagation_decay"] = updates["propagation_decay"]
    if "recency_half_life_days" in updates and updates["recency_half_life_days"] is not None:
        current_cfg["recency_half_life_days"] = updates["recency_half_life_days"]

    project.risk_config = current_cfg
    db.add(project)
    db.commit()
    db.refresh(project)

    ip = get_client_ip(request)
    log_audit(
        db,
        action="RISK_CONFIG_UPDATED",
        resource_type="project",
        resource_id=str(project.id),
        actor=user,
        details={"updated_keys": list(updates.keys())},
        ip_address=ip,
    )
    return project.risk_config


# --- Schedule Configuration Endpoints ---
@router.patch("/projects/{project_id}/schedule", response_model=dict)
def update_project_rescan_schedule(
    project_id: uuid.UUID,
    interval_hours: int = Query(ge=0, le=720),
    request: Request = None,
    user: User | None = Depends(get_optional_current_user),
    db: Session = Depends(get_db),
):
    project = get_project_or_404(db, project_id)
    if not check_project_membership(db, project_id, user, min_role="owner"):
        raise HTTPException(status_code=403, detail="Only project owners can configure rescan schedules.")

    project.rescan_interval_hours = interval_hours
    db.add(project)
    db.commit()
    db.refresh(project)

    ip = get_client_ip(request) if request else None
    log_audit(
        db,
        action="SCHEDULE_CONFIG_UPDATED",
        resource_type="project",
        resource_id=str(project.id),
        actor=user,
        details={"interval_hours": interval_hours},
        ip_address=ip,
    )
    return {"rescan_interval_hours": project.rescan_interval_hours}


# --- Historical Comparison Endpoint ---
@router.get("/projects/{project_id}/analysis-runs/{run_id}/compare/{target_run_id}", response_model=AnalysisComparisonOut)
def compare_runs_endpoint(
    project_id: uuid.UUID,
    run_id: uuid.UUID,
    target_run_id: uuid.UUID,
    user: User | None = Depends(get_optional_current_user),
    db: Session = Depends(get_db),
):
    project = get_project_or_404(db, project_id)
    if not check_project_membership(db, project_id, user, min_role="viewer"):
        raise HTTPException(status_code=403, detail="Access denied.")
    return compare_analysis_runs(db, project, base_run_id=run_id, target_run_id=target_run_id)


# --- Data Export Endpoints ---
@router.get("/projects/{project_id}/analysis-runs/{run_id}/export")
def export_analysis_data(
    project_id: uuid.UUID,
    run_id: uuid.UUID,
    format: Literal["json", "csv"] = "json",
    user: User | None = Depends(get_optional_current_user),
    db: Session = Depends(get_db),
):
    project = get_project_or_404(db, project_id)
    if not check_project_membership(db, project_id, user, min_role="viewer"):
        raise HTTPException(status_code=403, detail="Access denied.")

    run = db.get(AnalysisRun, run_id)
    if not run or run.project_id != project_id:
        raise AnalysisRunNotFoundError()

    resilience = db.query(ResilienceScore).filter(ResilienceScore.analysis_run_id == run.id).first()
    risk_scores = db.query(RiskScore).filter(RiskScore.analysis_run_id == run.id).all()
    knowledge_scores = db.query(KnowledgeScore).filter(KnowledgeScore.analysis_run_id == run.id).all()
    recs = db.query(Recommendation).filter(Recommendation.analysis_run_id == run.id).all()

    modules = {m.id: m.name for m in db.query(Module).all()}
    developers = {d.id: d.display_name for d in db.query(Developer).filter(Developer.project_id == project.id).all()}

    if format == "json":
        export_payload = {
            "project_id": str(project.id),
            "project_name": project.name,
            "analysis_run_id": str(run.id),
            "commit_sha": run.commit_sha,
            "status": run.status,
            "completed_at": run.completed_at.isoformat() if run.completed_at else None,
            "resilience": {
                "score": resilience.score if resilience else None,
                "label": resilience.label if resilience else None,
                "component_breakdown": resilience.component_breakdown if resilience else {},
            },
            "module_risks": [
                {
                    "module_id": str(r.module_id),
                    "module_name": modules.get(r.module_id, "Unknown"),
                    "risk_score": r.score,
                    "level": r.level,
                    "bus_factor": r.bus_factor,
                    "concentration_pct": r.concentration_pct,
                    "is_critical": r.is_critical_knowledge_area,
                    "factors": r.factors,
                }
                for r in risk_scores
            ],
            "knowledge_distribution": [
                {
                    "developer_id": str(k.developer_id),
                    "developer_name": developers.get(k.developer_id, "Unknown"),
                    "module_id": str(k.module_id),
                    "module_name": modules.get(k.module_id, "Unknown"),
                    "score": k.score,
                }
                for k in knowledge_scores
            ],
            "recommendations": [
                {
                    "severity": rec.severity,
                    "title": rec.title,
                    "description": rec.description,
                    "module_id": str(rec.module_id) if rec.module_id else None,
                }
                for rec in recs
            ],
        }
        return Response(
            content=json.dumps(export_payload, indent=2),
            media_type="application/json",
            headers={"Content-Disposition": f"attachment; filename=coderadar_{project.name}_{run.id}.json"},
        )

    # CSV export
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["module_name", "risk_score", "risk_level", "bus_factor", "concentration_pct", "is_critical"])
    for r in risk_scores:
        writer.writerow([
            modules.get(r.module_id, "Unknown"),
            r.score,
            r.level,
            r.bus_factor,
            r.concentration_pct,
            r.is_critical_knowledge_area,
        ])
    return Response(
        content=output.getvalue(),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename=coderadar_{project.name}_{run.id}.csv"},
    )
