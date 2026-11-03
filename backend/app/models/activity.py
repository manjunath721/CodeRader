import uuid
from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, Integer, JSON, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, GUID, TimestampMixin, UUIDMixin


class Commit(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "commits"
    # Makes incremental re-ingestion idempotent/retry-safe: re-processing a commit
    # we've already stored (e.g. after a crash mid-run) is a no-op, not a duplicate row.
    __table_args__ = (UniqueConstraint("repository_id", "hash", name="uq_commit_repo_hash"),)

    repository_id: Mapped[uuid.UUID] = mapped_column(GUID(), ForeignKey("repositories.id"), index=True)
    developer_id: Mapped[uuid.UUID | None] = mapped_column(GUID(), ForeignKey("developers.id"), nullable=True)
    hash: Mapped[str] = mapped_column(String(64), index=True)
    message: Mapped[str] = mapped_column(String(2000))
    authored_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    additions: Mapped[int] = mapped_column(Integer, default=0)
    deletions: Mapped[int] = mapped_column(Integer, default=0)
    files_changed_count: Mapped[int] = mapped_column(Integer, default=0)
    # Files touched by this commit, as module_id -> lines_changed. Kept denormalized
    # here (rather than a join table) since it's write-once at ingestion time and
    # read only in aggregate during knowledge-score computation.
    module_changes: Mapped[dict] = mapped_column(JSON, default=dict)


class PullRequest(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "pull_requests"

    repository_id: Mapped[uuid.UUID] = mapped_column(GUID(), ForeignKey("repositories.id"))
    author_id: Mapped[uuid.UUID | None] = mapped_column(GUID(), ForeignKey("developers.id"), nullable=True)
    number: Mapped[int] = mapped_column(Integer)
    title: Mapped[str] = mapped_column(String(500))
    merged_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    module_ids: Mapped[list] = mapped_column(JSON, default=list)

    reviews: Mapped[list["Review"]] = relationship(back_populates="pull_request")


class Review(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "reviews"

    pull_request_id: Mapped[uuid.UUID] = mapped_column(GUID(), ForeignKey("pull_requests.id"))
    reviewer_id: Mapped[uuid.UUID | None] = mapped_column(GUID(), ForeignKey("developers.id"), nullable=True)
    submitted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    state: Mapped[str] = mapped_column(String(30), default="approved")

    pull_request: Mapped["PullRequest"] = relationship(back_populates="reviews")


class Issue(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "issues"

    repository_id: Mapped[uuid.UUID] = mapped_column(GUID(), ForeignKey("repositories.id"))
    author_id: Mapped[uuid.UUID | None] = mapped_column(GUID(), ForeignKey("developers.id"), nullable=True)
    module_id: Mapped[uuid.UUID | None] = mapped_column(GUID(), ForeignKey("modules.id"), nullable=True)
    title: Mapped[str] = mapped_column(String(500))
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class DeveloperFileActivity(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "developer_file_activity"
    __table_args__ = (UniqueConstraint("developer_id", "file_id", name="uq_dev_file_activity"),)

    developer_id: Mapped[uuid.UUID] = mapped_column(GUID(), ForeignKey("developers.id"), index=True)
    file_id: Mapped[uuid.UUID] = mapped_column(GUID(), ForeignKey("files.id"), index=True)
    commits_count: Mapped[int] = mapped_column(Integer, default=0)
    lines_added: Mapped[int] = mapped_column(Integer, default=0)
    lines_deleted: Mapped[int] = mapped_column(Integer, default=0)
    last_commit_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class DeveloperModuleActivity(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "developer_module_activity"
    # This table holds current-state aggregates (not per-run history), so re-analysis
    # must upsert by this key rather than insert fresh duplicate rows each run.
    __table_args__ = (UniqueConstraint("developer_id", "module_id", name="uq_dev_module_activity"),)

    developer_id: Mapped[uuid.UUID] = mapped_column(GUID(), ForeignKey("developers.id"), index=True)
    module_id: Mapped[uuid.UUID] = mapped_column(GUID(), ForeignKey("modules.id"), index=True)
    commits_count: Mapped[int] = mapped_column(Integer, default=0)
    lines_changed: Mapped[int] = mapped_column(Integer, default=0)
    reviews_count: Mapped[int] = mapped_column(Integer, default=0)
    issues_count: Mapped[int] = mapped_column(Integer, default=0)
    last_activity_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
