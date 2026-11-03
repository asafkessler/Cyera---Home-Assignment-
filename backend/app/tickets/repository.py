"""Data access for tickets created through the app. Every query is scoped to one user."""
from sqlalchemy import select
from sqlalchemy.orm import Session as DbSession

from app.models import Ticket


def insert(
    db: DbSession,
    *,
    user_id: int,
    project_key: str,
    issue_key: str,
    issue_id: str,
    summary: str,
    issue_url: str,
    source: str,
) -> Ticket:
    ticket = Ticket(
        user_id=user_id,
        project_key=project_key,
        issue_key=issue_key,
        issue_id=issue_id,
        summary=summary,
        issue_url=issue_url,
        source=source,
    )
    db.add(ticket)
    db.commit()
    db.refresh(ticket)
    return ticket


def list_recent(db: DbSession, *, user_id: int, project_key: str, limit: int) -> list[Ticket]:
    """Newest first, for this user and project only."""
    stmt = (
        select(Ticket)
        .where(Ticket.user_id == user_id, Ticket.project_key == project_key)
        .order_by(Ticket.created_at.desc(), Ticket.id.desc())
        .limit(limit)
    )
    return list(db.scalars(stmt))
