import uuid

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.security import create_access_token, hash_password, verify_password
from app.models.auth import AuditLog, ProjectMember, User
from app.models.project import Project
from app.schemas.auth import AuditLogOut, ProjectMemberCreate, ProjectMemberOut, Token, UserLogin, UserOut, UserRegister
from app.services.auth_service import check_project_membership, get_client_ip, get_current_user, log_audit

router = APIRouter(prefix="/auth", tags=["auth"])
projects_auth_router = APIRouter(tags=["project-access"])


@router.post("/register", response_model=Token, status_code=201)
def register(payload: UserRegister, request: Request, db: Session = Depends(get_db)):
    existing = db.query(User).filter(User.email == payload.email.lower().strip()).first()
    if existing:
        raise HTTPException(status_code=400, detail="An account with this email already exists.")

    is_first_user = db.query(User).count() == 0
    user = User(
        email=payload.email.lower().strip(),
        hashed_password=hash_password(payload.password),
        full_name=payload.full_name,
        role="admin" if is_first_user else "user",
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    ip = get_client_ip(request)
    log_audit(
        db,
        action="USER_REGISTERED",
        resource_type="user",
        resource_id=str(user.id),
        actor=user,
        details={"email": user.email, "role": user.role},
        ip_address=ip,
    )

    token = create_access_token({"sub": str(user.id), "email": user.email, "role": user.role})
    return Token(access_token=token, token_type="bearer", user=UserOut.model_validate(user))


@router.post("/login", response_model=Token)
def login(payload: UserLogin, request: Request, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == payload.email.lower().strip()).first()
    if not user or not verify_password(payload.password, user.hashed_password):
        raise HTTPException(status_code=401, detail="Invalid email or password.")
    if not user.is_active:
        raise HTTPException(status_code=403, detail="Account is deactivated.")

    ip = get_client_ip(request)
    log_audit(
        db,
        action="USER_LOGGED_IN",
        resource_type="user",
        resource_id=str(user.id),
        actor=user,
        details={"email": user.email},
        ip_address=ip,
    )

    token = create_access_token({"sub": str(user.id), "email": user.email, "role": user.role})
    return Token(access_token=token, token_type="bearer", user=UserOut.model_validate(user))


@router.get("/me", response_model=UserOut)
def get_current_user_profile(user: User = Depends(get_current_user)):
    return user


# Project Members & Audit Logs
@projects_auth_router.get("/projects/{project_id}/members", response_model=list[ProjectMemberOut])
def list_project_members(
    project_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if not check_project_membership(db, project_id, user, min_role="viewer"):
        raise HTTPException(status_code=403, detail="Access denied to this project.")
    members = db.query(ProjectMember).filter(ProjectMember.project_id == project_id).all()
    out = []
    for m in members:
        u = db.get(User, m.user_id)
        out.append(
            ProjectMemberOut(
                id=m.id,
                project_id=m.project_id,
                user_id=m.user_id,
                role=m.role,
                email=u.email if u else None,
                full_name=u.full_name if u else None,
                created_at=m.created_at,
            )
        )
    return out


@projects_auth_router.post("/projects/{project_id}/members", response_model=ProjectMemberOut, status_code=201)
def add_project_member(
    project_id: uuid.UUID,
    payload: ProjectMemberCreate,
    request: Request,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if not check_project_membership(db, project_id, user, min_role="owner"):
        raise HTTPException(status_code=403, detail="Only project owners can manage members.")

    target_user = db.query(User).filter(User.email == payload.email.lower().strip()).first()
    if not target_user:
        raise HTTPException(status_code=404, detail="User with that email does not exist.")

    existing = (
        db.query(ProjectMember)
        .filter(ProjectMember.project_id == project_id, ProjectMember.user_id == target_user.id)
        .first()
    )
    if existing:
        existing.role = payload.role
        db.add(existing)
        db.commit()
        db.refresh(existing)
        return ProjectMemberOut(
            id=existing.id,
            project_id=existing.project_id,
            user_id=existing.user_id,
            role=existing.role,
            email=target_user.email,
            full_name=target_user.full_name,
            created_at=existing.created_at,
        )

    member = ProjectMember(
        project_id=project_id,
        user_id=target_user.id,
        role=payload.role,
    )
    db.add(member)
    db.commit()
    db.refresh(member)

    ip = get_client_ip(request)
    log_audit(
        db,
        action="MEMBER_ADDED",
        resource_type="project",
        resource_id=str(project_id),
        actor=user,
        details={"member_email": target_user.email, "role": payload.role},
        ip_address=ip,
    )

    return ProjectMemberOut(
        id=member.id,
        project_id=member.project_id,
        user_id=member.user_id,
        role=member.role,
        email=target_user.email,
        full_name=target_user.full_name,
        created_at=member.created_at,
    )


@projects_auth_router.delete("/projects/{project_id}/members/{target_user_id}", status_code=204)
def remove_project_member(
    project_id: uuid.UUID,
    target_user_id: uuid.UUID,
    request: Request,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if not check_project_membership(db, project_id, user, min_role="owner"):
        raise HTTPException(status_code=403, detail="Only project owners can manage members.")

    member = (
        db.query(ProjectMember)
        .filter(ProjectMember.project_id == project_id, ProjectMember.user_id == target_user_id)
        .first()
    )
    if member:
        db.delete(member)
        db.commit()
        ip = get_client_ip(request)
        log_audit(
            db,
            action="MEMBER_REMOVED",
            resource_type="project",
            resource_id=str(project_id),
            actor=user,
            details={"removed_user_id": str(target_user_id)},
            ip_address=ip,
        )
    return None


@projects_auth_router.get("/projects/{project_id}/audit-logs", response_model=list[AuditLogOut])
def get_project_audit_logs(
    project_id: uuid.UUID,
    limit: int = 50,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if not check_project_membership(db, project_id, user, min_role="analyst"):
        raise HTTPException(status_code=403, detail="Access denied.")
    logs = (
        db.query(AuditLog)
        .filter(
            (AuditLog.resource_id == str(project_id))
            | (AuditLog.resource_type == "project" and AuditLog.resource_id == str(project_id))
        )
        .order_by(AuditLog.created_at.desc())
        .limit(min(limit, 200))
        .all()
    )
    return logs
