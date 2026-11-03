"""
ORM models: the database schema.

Tenant isolation rule: every table that holds data belonging to a user has a
`user_id` column, and every query against it filters by that column (see the
repository modules). `users` and `sessions` are the only exceptions, because
they are what a tenant is resolved from.
"""
from datetime import datetime, timezone

from sqlalchemy import DateTime, ForeignKey, Index, String, Text, TypeDecorator
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class UTCDateTime(TypeDecorator):
    """
    Timezone-safe timestamps.

    SQLite has no timezone support and hands back naive datetimes, which then
    cannot be compared with aware ones. This type stores everything as UTC and
    re-attaches UTC on the way out, so application code only ever sees aware
    UTC datetimes regardless of the database engine.
    """

    impl = DateTime
    cache_ok = True

    def process_bind_param(self, value, _dialect):
        if value is None:
            return None
        if value.tzinfo is None:
            raise ValueError("naive datetime written to a UTCDateTime column")
        return value.astimezone(timezone.utc).replace(tzinfo=None)

    def process_result_value(self, value, _dialect):
        if value is None:
            return None
        return value.replace(tzinfo=timezone.utc)


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(320), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(100))
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)

    jira_connection: Mapped["JiraConnection | None"] = relationship(
        back_populates="user", uselist=False, cascade="all, delete-orphan"
    )


class Session(Base):
    """A server-side login session. The cookie holds the raw token; we store its hash."""

    __tablename__ = "sessions"

    id: Mapped[int] = mapped_column(primary_key=True)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)
    expires_at: Mapped[datetime] = mapped_column(UTCDateTime)
    last_seen_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)


class JiraConnection(Base):
    """One Jira Cloud workspace per user. The API token is stored encrypted."""

    __tablename__ = "jira_connections"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), unique=True)
    site_url: Mapped[str] = mapped_column(String(255))
    email: Mapped[str] = mapped_column(String(320))
    api_token_encrypted: Mapped[str] = mapped_column(Text)
    jira_account_id: Mapped[str] = mapped_column(String(128))
    display_name: Mapped[str] = mapped_column(String(255))
    connected_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)
    last_verified_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)

    user: Mapped[User] = relationship(back_populates="jira_connection")


class Ticket(Base):
    """A Jira issue created through this app (from the UI or the public API)."""

    __tablename__ = "tickets"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    project_key: Mapped[str] = mapped_column(String(64))
    issue_key: Mapped[str] = mapped_column(String(64))
    issue_id: Mapped[str] = mapped_column(String(64))
    summary: Mapped[str] = mapped_column(String(255))
    issue_url: Mapped[str] = mapped_column(String(512))
    source: Mapped[str] = mapped_column(String(8))  # "ui" | "api"
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)

    __table_args__ = (
        # The recent-tickets query: this user, this project, newest first.
        Index("ix_tickets_user_project_created", "user_id", "project_key", "created_at"),
    )


class ApiKey(Base):
    """A per-user API key for the public API. Only the hash is stored."""

    __tablename__ = "api_keys"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(100))
    key_prefix: Mapped[str] = mapped_column(String(12))  # shown in the UI to identify the key
    key_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)
    last_used_at: Mapped[datetime | None] = mapped_column(UTCDateTime, nullable=True)
    revoked_at: Mapped[datetime | None] = mapped_column(UTCDateTime, nullable=True)
