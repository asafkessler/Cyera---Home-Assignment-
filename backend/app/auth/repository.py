"""Data access for users and sessions. No business rules here, only queries."""
from datetime import datetime

from sqlalchemy import delete, select
from sqlalchemy.orm import Session as DbSession

from app.models import Session, User, utcnow


def get_user_by_email(db: DbSession, email: str) -> User | None:
    return db.scalar(select(User).where(User.email == email))


def get_user_by_id(db: DbSession, user_id: int) -> User | None:
    return db.get(User, user_id)


def create_user(db: DbSession, *, email: str, password_hash: str) -> User:
    user = User(email=email, password_hash=password_hash)
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def create_session(db: DbSession, *, user_id: int, token_hash: str, expires_at: datetime) -> Session:
    session = Session(user_id=user_id, token_hash=token_hash, expires_at=expires_at)
    db.add(session)
    db.commit()
    return session


def get_live_session(db: DbSession, token_hash: str) -> Session | None:
    """A session that exists and has not expired."""
    return db.scalar(
        select(Session).where(Session.token_hash == token_hash, Session.expires_at > utcnow())
    )


def touch_session(db: DbSession, session: Session) -> None:
    session.last_seen_at = utcnow()
    db.commit()


def delete_session(db: DbSession, token_hash: str) -> None:
    db.execute(delete(Session).where(Session.token_hash == token_hash))
    db.commit()


def delete_expired_sessions(db: DbSession) -> int:
    result = db.execute(delete(Session).where(Session.expires_at <= utcnow()))
    db.commit()
    return result.rowcount
