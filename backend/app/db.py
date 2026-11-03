"""
Database engine and session management.

The rest of the app depends on `get_db` (a FastAPI dependency yielding a
SQLAlchemy session) and never on the engine directly, so the engine can be
swapped (SQLite today, PostgreSQL tomorrow) by changing DATABASE_URL.
"""
from collections.abc import Iterator
from pathlib import Path

from sqlalchemy import create_engine, event
from sqlalchemy.engine import Engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.config import get_settings


class Base(DeclarativeBase):
    """Declarative base all ORM models inherit from."""


def _build_engine() -> Engine:
    settings = get_settings()
    connect_args: dict = {}

    if settings.is_sqlite:
        # FastAPI may hand a connection to a different thread than the one
        # that created it; SQLite forbids that by default.
        connect_args["check_same_thread"] = False
        # Make sure the directory for the database file exists.
        path = settings.database_url.removeprefix("sqlite:///")
        if path and path != ":memory:":
            Path(path).parent.mkdir(parents=True, exist_ok=True)

    engine = create_engine(settings.database_url, connect_args=connect_args)

    if settings.is_sqlite:
        @event.listens_for(engine, "connect")
        def _configure_sqlite(dbapi_connection, _record) -> None:
            cursor = dbapi_connection.cursor()
            # WAL: readers do not block the writer and vice versa.
            cursor.execute("PRAGMA journal_mode=WAL")
            # Wait up to 5s for a lock instead of failing immediately.
            cursor.execute("PRAGMA busy_timeout=5000")
            # SQLite ignores foreign keys unless told otherwise.
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.close()

    return engine


engine = _build_engine()
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


def get_db() -> Iterator[Session]:
    """FastAPI dependency: one session per request, always closed."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db() -> None:
    """Create tables that do not exist yet. Fine for a POC; production would use migrations."""
    from app import models  # noqa: F401  (import registers the models on Base)

    Base.metadata.create_all(bind=engine)
