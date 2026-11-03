import uuid
from datetime import datetime, timezone

from sqlalchemy import DateTime
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import CHAR, TypeDecorator

from app.core.db import Base


class GUID(TypeDecorator):
    """Portable UUID type: stores as native UUID on Postgres, CHAR(36) on SQLite
    (used only in the test suite — production runs on Postgres per docker-compose.yml).
    """

    impl = CHAR
    cache_ok = True

    def load_dialect_impl(self, dialect):
        if dialect.name == "postgresql":
            from sqlalchemy.dialects.postgresql import UUID as PG_UUID

            return dialect.type_descriptor(PG_UUID(as_uuid=True))
        return dialect.type_descriptor(CHAR(36))

    def process_bind_param(self, value, dialect):
        if value is None:
            return value
        if dialect.name == "postgresql":
            return str(value)
        return str(value)

    def process_result_value(self, value, dialect):
        if value is None:
            return value
        return uuid.UUID(str(value))


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )


class UUIDMixin:
    id: Mapped[uuid.UUID] = mapped_column(GUID(), primary_key=True, default=uuid.uuid4)


__all__ = ["Base", "GUID", "TimestampMixin", "UUIDMixin"]
