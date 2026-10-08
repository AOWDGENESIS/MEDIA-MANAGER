"""SQLAlchemy Declarative Base + gemeinsame Mixins."""
from __future__ import annotations

import datetime as dt

from sqlalchemy import DateTime
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class TimestampMixin:
    created_at: Mapped[dt.datetime] = mapped_column(
        DateTime, default=lambda: dt.datetime.now(dt.UTC)
    )
    updated_at: Mapped[dt.datetime] = mapped_column(
        DateTime,
        default=lambda: dt.datetime.now(dt.UTC),
        onupdate=lambda: dt.datetime.now(dt.UTC),
    )
