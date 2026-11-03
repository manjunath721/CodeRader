import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict


class ProjectCreate(BaseModel):
    name: str
    description: str | None = None


class ProjectOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    name: str
    description: str | None
    is_demo: bool
    created_at: datetime


class RepositoryCreate(BaseModel):
    url: str
    provider: str = "git"  # git|github|local


class RepositoryOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    project_id: uuid.UUID
    url: str
    provider: str
    default_branch: str
    total_files: int
    contributor_count: int
    commit_count: int
    last_analyzed_at: str | None


class AnalysisRunOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    project_id: uuid.UUID
    status: str
    stage_status: dict
    progress: dict
    scan_mode: str
    cancel_requested: bool
    started_at: datetime | None
    completed_at: datetime | None
    error_message: str | None
