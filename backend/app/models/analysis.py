import uuid
from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, Index, JSON, String, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, GUID, TimestampMixin, UUIDMixin

_ACTIVE_STATUS_FILTER = text("status IN ('pending', 'running')")


class AnalysisRun(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "analysis_runs"
    __table_args__ = (
        # The actual concurrency guarantee (app/api/projects.py has a
        # friendly pre-check, but this is what makes it race-proof). Declared
        # here — not only in the Alembic migration — so it exists on ANY
        # engine built from this model's metadata, including
        # Base.metadata.create_all() used by the test suite; a constraint
        # that only lives in a migration script is invisible to, and
        # silently absent from, every test that doesn't run migrations.
        Index(
            "uq_one_active_run_per_project", "project_id", unique=True,
            sqlite_where=_ACTIVE_STATUS_FILTER, postgresql_where=_ACTIVE_STATUS_FILTER,
        ),
    )

    project_id: Mapped[uuid.UUID] = mapped_column(GUID(), ForeignKey("projects.id"), index=True)
    # pending|running|complete|failed|cancelled
    status: Mapped[str] = mapped_column(String(30), default="pending")
    stage_status: Mapped[dict] = mapped_column(JSON, default=dict)
    # Per-stage progress counters the frontend polls (files processed, commits processed,
    # skipped files, errors) — perf/observability work, never fabricated: only written
    # by the pipeline as real work completes.
    progress: Mapped[dict] = mapped_column(JSON, default=dict)
    scan_mode: Mapped[str] = mapped_column(String(20), default="full")  # "quick" | "full"
    rescan_type: Mapped[str] = mapped_column(String(30), default="full")  # "full" | "incremental" | "quick"
    commit_sha: Mapped[str | None] = mapped_column(String(64), nullable=True)
    cancel_requested: Mapped[bool] = mapped_column(default=False)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    error_message: Mapped[str | None] = mapped_column(String(2000), nullable=True)

    project: Mapped["Project"] = relationship(back_populates="analysis_runs")


class KnowledgeScore(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "knowledge_scores"

    analysis_run_id: Mapped[uuid.UUID] = mapped_column(GUID(), ForeignKey("analysis_runs.id"))
    developer_id: Mapped[uuid.UUID] = mapped_column(GUID(), ForeignKey("developers.id"))
    module_id: Mapped[uuid.UUID] = mapped_column(GUID(), ForeignKey("modules.id"))
    score: Mapped[float] = mapped_column(Float)  # 0-100
    component_breakdown: Mapped[dict] = mapped_column(JSON, default=dict)
    computed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class RiskScore(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "risk_scores"

    analysis_run_id: Mapped[uuid.UUID] = mapped_column(GUID(), ForeignKey("analysis_runs.id"))
    module_id: Mapped[uuid.UUID] = mapped_column(GUID(), ForeignKey("modules.id"))
    score: Mapped[float] = mapped_column(Float)  # 0-100
    level: Mapped[str] = mapped_column(String(20))  # LOW|MODERATE|HIGH|CRITICAL
    factors: Mapped[dict] = mapped_column(JSON, default=dict)
    criticality_score: Mapped[float] = mapped_column(Float, default=0.0)
    is_critical_knowledge_area: Mapped[bool] = mapped_column(default=False)
    bus_factor: Mapped[int] = mapped_column(default=0)
    concentration_pct: Mapped[float] = mapped_column(Float, default=0.0)
    computed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class ResilienceScore(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "resilience_scores"

    analysis_run_id: Mapped[uuid.UUID] = mapped_column(GUID(), ForeignKey("analysis_runs.id"))
    project_id: Mapped[uuid.UUID] = mapped_column(GUID(), ForeignKey("projects.id"))
    score: Mapped[float] = mapped_column(Float)  # 0-100
    label: Mapped[str] = mapped_column(String(20))  # GOOD|MODERATE|AT_RISK|CRITICAL
    component_breakdown: Mapped[dict] = mapped_column(JSON, default=dict)
    computed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
