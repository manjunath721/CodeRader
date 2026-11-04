import uuid

from sqlalchemy import JSON, Boolean, Float, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, GUID, TimestampMixin, UUIDMixin


class Module(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "modules"
    __table_args__ = (UniqueConstraint("repository_id", "path_prefix", name="uq_module_repo_path"),)

    repository_id: Mapped[uuid.UUID] = mapped_column(GUID(), ForeignKey("repositories.id"), index=True)
    name: Mapped[str] = mapped_column(String(255))
    path_prefix: Mapped[str] = mapped_column(String(1000))
    loc: Mapped[int] = mapped_column(Integer, default=0)
    complexity_avg: Mapped[float] = mapped_column(Float, default=0.0)
    documentation_score: Mapped[float] = mapped_column(Float, default=0.0)  # 0-1
    change_frequency_90d: Mapped[int] = mapped_column(Integer, default=0)

    files: Mapped[list["File"]] = relationship(back_populates="module")


class File(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "files"
    # Enables upsert-by-path across incremental re-analysis instead of delete+recreate,
    # and is the lookup key for content-hash based analysis caching (perf work).
    __table_args__ = (UniqueConstraint("repository_id", "path", name="uq_file_repo_path"),)

    repository_id: Mapped[uuid.UUID] = mapped_column(GUID(), ForeignKey("repositories.id"), index=True)
    module_id: Mapped[uuid.UUID | None] = mapped_column(GUID(), ForeignKey("modules.id"), nullable=True)
    path: Mapped[str] = mapped_column(String(1000))
    language: Mapped[str | None] = mapped_column(String(50), nullable=True)
    size_bytes: Mapped[int] = mapped_column(Integer, default=0)
    is_test: Mapped[bool] = mapped_column(Boolean, default=False)
    is_config: Mapped[bool] = mapped_column(Boolean, default=False)
    complexity: Mapped[float] = mapped_column(Float, default=0.0)
    doc_coverage_pct: Mapped[float] = mapped_column(Float, default=0.0)
    lines_of_code: Mapped[int] = mapped_column(Integer, default=0)
    # --- Analysis caching (perf work) ---
    content_hash: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    analyzer_version: Mapped[str | None] = mapped_column(String(20), nullable=True)
    # raw import strings, used for module-dependency extraction
    import_targets: Mapped[list] = mapped_column(JSON, default=list)

    module: Mapped["Module"] = relationship(back_populates="files")


class ModuleDependency(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "module_dependencies"
    __table_args__ = (
        UniqueConstraint("module_id", "depends_on_module_id", name="uq_module_dependency_edge"),
    )

    module_id: Mapped[uuid.UUID] = mapped_column(GUID(), ForeignKey("modules.id"), index=True)
    depends_on_module_id: Mapped[uuid.UUID] = mapped_column(GUID(), ForeignKey("modules.id"), index=True)
    weight: Mapped[float] = mapped_column(Float, default=1.0)
    # "import" (auto-detected from source imports) | "manual" (user/demo-seeded)
    source: Mapped[str] = mapped_column(String(20), default="import")


class Technology(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "technologies"

    name: Mapped[str] = mapped_column(String(100), unique=True)
    category: Mapped[str] = mapped_column(String(30), default="language")  # language|framework|db|infra


class DeveloperTechnology(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "developer_technologies"

    developer_id: Mapped[uuid.UUID] = mapped_column(GUID(), ForeignKey("developers.id"))
    technology_id: Mapped[uuid.UUID] = mapped_column(GUID(), ForeignKey("technologies.id"))
    overlap_score: Mapped[float] = mapped_column(Float, default=0.0)
