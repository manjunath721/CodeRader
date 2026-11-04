import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.models.developer import Developer
from app.models.code import Module
from app.services.query_service import build_developer_detail, build_module_detail, DeveloperNotFoundError, ModuleNotFoundError

router = APIRouter(tags=["developers-modules"])


@router.get("/developers/{developer_id}")
def get_developer(developer_id: uuid.UUID, db: Session = Depends(get_db)):
    dev = db.get(Developer, developer_id)
    if not dev:
        raise DeveloperNotFoundError()
    from app.models.project import Project

    project = db.get(Project, dev.project_id)
    return build_developer_detail(db, project, developer_id)


@router.get("/developers/{developer_id}/aliases")
def get_developer_aliases(developer_id: uuid.UUID, db: Session = Depends(get_db)):
    dev = db.get(Developer, developer_id)
    if not dev:
        raise DeveloperNotFoundError()
    from app.models.developer import DeveloperAlias
    aliases = db.query(DeveloperAlias).filter(DeveloperAlias.developer_id == developer_id).all()
    return [
        {
            "id": str(a.id),
            "raw_name": a.raw_name,
            "raw_email": a.raw_email,
            "confidence": a.confidence,
            "confirmed": a.confirmed,
        }
        for a in aliases
    ]


@router.post("/developers/{developer_id}/aliases/{alias_id}/confirm")
def confirm_developer_alias(developer_id: uuid.UUID, alias_id: uuid.UUID, db: Session = Depends(get_db)):
    dev = db.get(Developer, developer_id)
    if not dev:
        raise DeveloperNotFoundError()
    from app.models.developer import DeveloperAlias
    alias = db.get(DeveloperAlias, alias_id)
    if not alias:
        raise DeveloperNotFoundError()
    alias.developer_id = dev.id
    alias.confirmed = True
    alias.confidence = "exact"
    db.add(alias)
    db.commit()
    return {"status": "confirmed", "developer_id": str(dev.id), "alias_id": str(alias.id)}


@router.get("/modules/{module_id}")
def get_module(module_id: uuid.UUID, db: Session = Depends(get_db)):
    module = db.get(Module, module_id)
    if not module:
        raise ModuleNotFoundError()
    from app.models.project import Project, Repository

    repo = db.get(Repository, module.repository_id)
    project = db.get(Project, repo.project_id)
    return build_module_detail(db, project, module_id)
