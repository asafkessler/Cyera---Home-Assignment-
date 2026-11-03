"""Data access for Jira connections. Every function is scoped to one user."""
from sqlalchemy import select
from sqlalchemy.orm import Session as DbSession

from app.models import JiraConnection, utcnow


def get_connection(db: DbSession, user_id: int) -> JiraConnection | None:
    return db.scalar(select(JiraConnection).where(JiraConnection.user_id == user_id))


def upsert_connection(
    db: DbSession,
    user_id: int,
    *,
    site_url: str,
    email: str,
    api_token_encrypted: str,
    jira_account_id: str,
    display_name: str,
) -> JiraConnection:
    """Create the user's connection, or replace it if one exists (one workspace per user)."""
    connection = get_connection(db, user_id)
    if connection is None:
        connection = JiraConnection(user_id=user_id)
        db.add(connection)
    now = utcnow()
    connection.site_url = site_url
    connection.email = email
    connection.api_token_encrypted = api_token_encrypted
    connection.jira_account_id = jira_account_id
    connection.display_name = display_name
    connection.connected_at = now
    connection.last_verified_at = now
    db.commit()
    db.refresh(connection)
    return connection


def delete_connection(db: DbSession, user_id: int) -> bool:
    connection = get_connection(db, user_id)
    if connection is None:
        return False
    db.delete(connection)
    db.commit()
    return True
