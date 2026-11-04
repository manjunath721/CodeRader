import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class ProjectCreate(BaseModel):
    name: str
    description: str | None = None
    risk_config: dict | None = None


class ProjectRiskConfigUpdate(BaseModel):
    risk_weights: dict[str, float] | None = None
    knowledge_weights: dict[str, float] | None = None
    bus_factor_threshold: int | None = None
    criticality_threshold: float | None = None
    propagation_decay: float | None = None
    recency_half_life_days: int | None = None


class ProjectOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    name: str
    description: str | None
    is_demo: bool
    risk_config: dict
    rescan_interval_hours: int = 0
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
    last_indexed_commit_sha: str | None = None
    last_indexed_branch: str | None = None


class AnalysisRunOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    project_id: uuid.UUID
    status: str
    stage_status: dict
    progress: dict
    scan_mode: str
    rescan_type: str = "full"
    commit_sha: str | None = None
    cancel_requested: bool
    started_at: datetime | None
    completed_at: datetime | None
    error_message: str | None


class AnalyzeRequest(BaseModel):
    scan_mode: str = "full"  # "quick" | "full" | "incremental"
    force_full_rescan: bool = False


class ModuleRiskDelta(BaseModel):
    module_id: str
    name: str
    old_score: float | None = None
    new_score: float | None = None
    delta: float = 0.0
    old_level: str | None = None
    new_level: str | None = None


class AnalysisComparisonOut(BaseModel):
    base_run_id: uuid.UUID
    target_run_id: uuid.UUID
    base_commit_sha: str | None = None
    target_commit_sha: str | None = None
    resilience_before: float | None = None
    resilience_after: float | None = None
    resilience_delta: float = 0.0
    label_before: str | None = None
    label_after: str | None = None
    modules_added: list[str] = Field(default_factory=list)
    modules_removed: list[str] = Field(default_factory=list)
    risk_changes: list[ModuleRiskDelta] = Field(default_factory=list)
    newly_introduced_risks: list[str] = Field(default_factory=list)
    resolved_risks: list[str] = Field(default_factory=list)
