"""
Authentication use cases: register, login, logout, resolve a session.

The session token handed to the browser is random and opaque; the database
holds only its hash. Revoking a session is therefore just deleting a row.
"""
from datetime import timedelta

from sqlalchemy.orm import Session as DbSession

from app.auth import repository
from app.config import get_settings
from app.core.errors import EmailAlreadyRegistered, InvalidCredentials
from app.core.security import generate_secret, hash_password, hash_secret, verify_password
from app.models import User, utcnow

# A real bcrypt hash of a throwaway password. Used so that a login attempt
# for an unknown email costs the same time as one for a known email; otherwise
# response timing would reveal which emails are registered.
_DUMMY_HASH = hash_password("timing-equalizer")


def register(db: DbSession, *, email: str, password: str) -> User:
    if repository.get_user_by_email(db, email) is not None:
        raise EmailAlreadyRegistered()
    return repository.create_user(db, email=email, password_hash=hash_password(password))


def login(db: DbSession, *, email: str, password: str) -> tuple[User, str]:
    """Verify credentials and open a session. Returns the user and the raw session token."""
    user = repository.get_user_by_email(db, email)
    if user is None:
        verify_password(password, _DUMMY_HASH)
        raise InvalidCredentials()
    if not verify_password(password, user.password_hash):
        raise InvalidCredentials()
    return user, open_session(db, user)


def open_session(db: DbSession, user: User) -> str:
    """Create a session row for `user` and return the raw token for the cookie."""
    token = generate_secret()
    ttl = timedelta(hours=get_settings().session_ttl_hours)
    repository.create_session(db, user_id=user.id, token_hash=hash_secret(token), expires_at=utcnow() + ttl)
    return token


def logout(db: DbSession, token: str) -> None:
    repository.delete_session(db, hash_secret(token))


def resolve_session(db: DbSession, token: str) -> User | None:
    """Map a raw cookie token to its user, or None if unknown or expired."""
    session = repository.get_live_session(db, hash_secret(token))
    if session is None:
        return None
    repository.touch_session(db, session)
    return repository.get_user_by_id(db, session.user_id)
