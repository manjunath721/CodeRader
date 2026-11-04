import uuid

from sqlalchemy import JSON, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, GUID, TimestampMixin, UUIDMixin

DEFAULT_RISK_CONFIG = {
    "risk_weights": {
        "knowledge_concentration": 0.25,
        "bus_factor_risk": 0.20,
        "documentation_risk": 0.15,
        "complexity_risk": 0.15,
        "change_frequency_risk": 0.15,
        "dependency_risk": 0.10,
    },
    "knowledge_weights": {
        "contribution": 0.35,
        "recency": 0.15,
        "module_experience": 0.20,
        "review": 0.20,
        "issue": 0.10,
    },
    "bus_factor_threshold": 10,
    "criticality_threshold": 70,
    "propagation_decay": 0.6,
    "recency_half_life_days": 90,
}


class Project(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "projects"

    name: Mapped[str] = mapped_column(String(255))
    description: Mapped[str | None] = mapped_column(String(2000), nullable=True)
    risk_config: Mapped[dict] = mapped_column(JSON, default=lambda: dict(DEFAULT_RISK_CONFIG))
    is_demo: Mapped[bool] = mapped_column(default=False)
    rescan_interval_hours: Mapped[int] = mapped_column(Integer, default=0)

    repositories: Mapped[list["Repository"]] = relationship(back_populates="project", cascade="all, delete-orphan")
    developers: Mapped[list["Developer"]] = relationship(back_populates="project", cascade="all, delete-orphan")
    analysis_runs: Mapped[list["AnalysisRun"]] = relationship(back_populates="project", cascade="all, delete-orphan")


class Repository(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "repositories"

    project_id: Mapped[uuid.UUID] = mapped_column(GUID(), ForeignKey("projects.id"))
    url: Mapped[str] = mapped_column(String(1000))
    provider: Mapped[str] = mapped_column(String(20), default="git")  # git|github|local
    default_branch: Mapped[str] = mapped_column(String(255), default="main")
    total_files: Mapped[int] = mapped_column(Integer, default=0)
    contributor_count: Mapped[int] = mapped_column(Integer, default=0)
    commit_count: Mapped[int] = mapped_column(Integer, default=0)
    last_analyzed_at: Mapped[str | None] = mapped_column(String(64), nullable=True)

    # --- Incremental indexing state (perf work: never re-walk history we've already ingested) ---
    last_indexed_commit_sha: Mapped[str | None] = mapped_column(String(64), nullable=True)
    last_indexed_branch: Mapped[str | None] = mapped_column(String(255), nullable=True)
    scan_mode: Mapped[str] = mapped_column(String(20), default="full")  # "quick" | "full"

    project: Mapped["Project"] = relationship(back_populates="repositories")
