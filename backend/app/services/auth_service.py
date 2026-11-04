import uuid
from typing import Callable

from fastapi import Depends, Header, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.db import get_db
from app.core.security import decode_access_token
from app.models.auth import AuditLog, ProjectMember, User
from app.models.project import Project

settings = get_settings()
security_bearer = HTTPBearer(auto_error=False)


def get_client_ip(request: Request) -> str | None:
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else None


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(security_bearer),
    db: Session = Depends(get_db),
) -> User:
    if not credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
            headers={"WWW-Authenticate": "Bearer"},
        )
    payload = decode_access_token(credentials.credentials)
    if not payload or "sub" not in payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    user_id = payload["sub"]
    user = db.query(User).filter(User.id == user_id, User.is_active.is_(True)).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found or inactive",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return user


def get_optional_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(security_bearer),
    db: Session = Depends(get_db),
) -> User | None:
    if not credentials:
        return None
    payload = decode_access_token(credentials.credentials)
    if not payload or "sub" not in payload:
        return None
    user_id = payload["sub"]
    return db.query(User).filter(User.id == user_id, User.is_active.is_(True)).first()


def check_project_membership(
    db: Session,
    project_id: uuid.UUID,
    user: User | None,
    min_role: str = "viewer",
) -> bool:
    """
    Role hierarchy: admin (superuser) > owner > analyst > viewer.
    Demo projects allow viewer access anonymously.
    """
    project = db.get(Project, project_id)
    if not project:
        return False
    if project.is_demo and min_role == "viewer":
        return True

    # If project has no assigned members yet (e.g. legacy/open mode or initial dev test), allow access
    has_any_members = db.query(ProjectMember).filter(ProjectMember.project_id == project_id).count() > 0
    if not has_any_members:
        return True

    if not user:
        if settings.ALLOW_ANONYMOUS_READS and min_role == "viewer":
            return True
        return False
    if user.role == "admin":
        return True

    member = (
        db.query(ProjectMember)
        .filter(ProjectMember.project_id == project_id, ProjectMember.user_id == user.id)
        .first()
    )
    if not member:
        return False

    roles = ["viewer", "analyst", "owner"]
    try:
        user_level = roles.index(member.role)
        required_level = roles.index(min_role)
        return user_level >= required_level
    except ValueError:
        return False


def log_audit(
    db: Session,
    action: str,
    resource_type: str,
    resource_id: str | None = None,
    actor: User | None = None,
    details: dict | None = None,
    ip_address: str | None = None,
) -> AuditLog:
    log_entry = AuditLog(
        actor_id=actor.id if actor else None,
        actor_email=actor.email if actor else "system/anonymous",
        action=action,
        resource_type=resource_type,
        resource_id=resource_id,
        details=details or {},
        ip_address=ip_address,
    )
    db.add(log_entry)
    db.commit()
    db.refresh(log_entry)
    return log_entry
