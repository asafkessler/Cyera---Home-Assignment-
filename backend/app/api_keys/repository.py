"""Data access for API keys. Every function that returns keys is scoped to one user."""
from sqlalchemy import select
from sqlalchemy.orm import Session as DbSession

from app.models import ApiKey, utcnow


def create(db: DbSession, *, user_id: int, name: str, key_prefix: str, key_hash: str) -> ApiKey:
    api_key = ApiKey(user_id=user_id, name=name, key_prefix=key_prefix, key_hash=key_hash)
    db.add(api_key)
    db.commit()
    db.refresh(api_key)
    return api_key


def list_for_user(db: DbSession, user_id: int) -> list[ApiKey]:
    stmt = select(ApiKey).where(ApiKey.user_id == user_id).order_by(ApiKey.created_at.desc(), ApiKey.id.desc())
    return list(db.scalars(stmt))


def get_for_user(db: DbSession, user_id: int, key_id: int) -> ApiKey | None:
    return db.scalar(select(ApiKey).where(ApiKey.user_id == user_id, ApiKey.id == key_id))


def get_active_by_hash(db: DbSession, key_hash: str) -> ApiKey | None:
    """Lookup used on every public-API request. Revoked keys never match."""
    return db.scalar(select(ApiKey).where(ApiKey.key_hash == key_hash, ApiKey.revoked_at.is_(None)))


def mark_used(db: DbSession, api_key: ApiKey) -> None:
    api_key.last_used_at = utcnow()
    db.commit()


def revoke(db: DbSession, api_key: ApiKey) -> None:
    api_key.revoked_at = utcnow()
    db.commit()
