"""
API key use cases.

A key is a random secret with a recognisable prefix. The database stores its
SHA-256 hash, so a leaked database does not yield working keys, and the user
sees the full key exactly once, at creation.
"""
from sqlalchemy.orm import Session as DbSession

from app.api_keys import repository
from app.auth import repository as users
from app.core.errors import NotFound
from app.core.security import generate_secret, hash_secret
from app.models import ApiKey, User

KEY_PREFIX = "ihk_"          # "IdentityHub key": makes keys easy to spot in logs and secret scanners
DISPLAY_PREFIX_LENGTH = 12   # enough to tell keys apart, far too short to be useful


def create_key(db: DbSession, user: User, *, name: str) -> tuple[ApiKey, str]:
    raw_key = KEY_PREFIX + generate_secret(32)
    api_key = repository.create(
        db,
        user_id=user.id,
        name=name,
        key_prefix=raw_key[:DISPLAY_PREFIX_LENGTH],
        key_hash=hash_secret(raw_key),
    )
    return api_key, raw_key


def list_keys(db: DbSession, user: User) -> list[ApiKey]:
    return repository.list_for_user(db, user.id)


def revoke_key(db: DbSession, user: User, key_id: int) -> None:
    api_key = repository.get_for_user(db, user.id, key_id)
    if api_key is None:
        raise NotFound("API key not found.")
    if api_key.revoked_at is None:
        repository.revoke(db, api_key)


def resolve_key(db: DbSession, raw_key: str) -> User | None:
    """Map a presented key to its owner, or None if unknown or revoked. Records last use."""
    api_key = repository.get_active_by_hash(db, hash_secret(raw_key))
    if api_key is None:
        return None
    repository.mark_used(db, api_key)
    return users.get_user_by_id(db, api_key.user_id)
