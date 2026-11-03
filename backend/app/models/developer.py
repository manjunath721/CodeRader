import uuid

from sqlalchemy import ForeignKey, String, Boolean
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, GUID, TimestampMixin, UUIDMixin


class Developer(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "developers"

    project_id: Mapped[uuid.UUID] = mapped_column(GUID(), ForeignKey("projects.id"))
    display_name: Mapped[str] = mapped_column(String(255))
    primary_email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    normalized_key: Mapped[str] = mapped_column(String(255), index=True)

    project: Mapped["Project"] = relationship(back_populates="developers")
    aliases: Mapped[list["DeveloperAlias"]] = relationship(back_populates="developer", cascade="all, delete-orphan")


class DeveloperAlias(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "developer_aliases"

    developer_id: Mapped[uuid.UUID] = mapped_column(GUID(), ForeignKey("developers.id"))
    raw_name: Mapped[str] = mapped_column(String(255))
    raw_email: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)
    source: Mapped[str] = mapped_column(String(20), default="git")  # git|github
    confidence: Mapped[str] = mapped_column(String(20), default="exact")  # exact|suggested
    confirmed: Mapped[bool] = mapped_column(Boolean, default=True)

    developer: Mapped["Developer"] = relationship(back_populates="aliases")
