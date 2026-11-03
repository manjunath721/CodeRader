import uuid
from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, JSON, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, GUID, TimestampMixin, UUIDMixin


class Simulation(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "simulations"

    project_id: Mapped[uuid.UUID] = mapped_column(GUID(), ForeignKey("projects.id"))
    type: Mapped[str] = mapped_column(String(20))  # single|multiple
    developer_ids: Mapped[list] = mapped_column(JSON, default=list)
    requested_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    status: Mapped[str] = mapped_column(String(20), default="complete")


class SimulationResult(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "simulation_results"

    simulation_id: Mapped[uuid.UUID] = mapped_column(GUID(), ForeignKey("simulations.id"))
    resilience_before: Mapped[float] = mapped_column(Float)
    resilience_after: Mapped[float] = mapped_column(Float)
    knowledge_impact_pct: Mapped[float] = mapped_column(Float)
    affected_modules: Mapped[list] = mapped_column(JSON, default=list)
    backup_candidates: Mapped[dict] = mapped_column(JSON, default=dict)
    risk_propagation: Mapped[dict] = mapped_column(JSON, default=dict)


class Recommendation(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "recommendations"

    project_id: Mapped[uuid.UUID] = mapped_column(GUID(), ForeignKey("projects.id"))
    module_id: Mapped[uuid.UUID | None] = mapped_column(GUID(), ForeignKey("modules.id"), nullable=True)
    analysis_run_id: Mapped[uuid.UUID] = mapped_column(GUID(), ForeignKey("analysis_runs.id"))
    severity: Mapped[str] = mapped_column(String(20))  # CRITICAL|HIGH|MODERATE
    title: Mapped[str] = mapped_column(String(500))
    description: Mapped[str] = mapped_column(String(2000))
    related_developer_id: Mapped[uuid.UUID | None] = mapped_column(GUID(), ForeignKey("developers.id"), nullable=True)
