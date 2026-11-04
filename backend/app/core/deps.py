"""
FastAPI dependencies shared by routers.

A dependency is a function FastAPI calls to produce a value for a route
parameter. Centralising them here means a route declares *what* it needs
(a database session, the logged-in user) and never *how* to get it.
"""
from typing import Annotated

from fastapi import Depends, Request
from fastapi.security import APIKeyHeader
from sqlalchemy.orm import Session

from app.auth import service as auth_service
from app.config import Settings, get_settings
from app.api_keys import service as api_key_service
from app.core.errors import InvalidApiKey, NotAuthenticated
from app.core.security import CredentialCipher
from app.db import get_db
from app.models import User

DbSession = Annotated[Session, Depends(get_db)]
AppSettings = Annotated[Settings, Depends(get_settings)]


def get_cipher(settings: AppSettings) -> CredentialCipher:
    return CredentialCipher(settings.app_encryption_key)


Cipher = Annotated[CredentialCipher, Depends(get_cipher)]


def get_current_user(request: Request, db: DbSession, settings: AppSettings) -> User:
    """
    Resolve the session cookie to a user, or fail with 401.

    This is the only place the cookie is read. Routes receive a `User` and
    never a user id from the request, which is what makes tenant isolation
    hard to get wrong: there is no way to ask for someone else's data.
    """
    token = request.cookies.get(settings.session_cookie_name)
    if not token:
        raise NotAuthenticated()
    user = auth_service.resolve_session(db, token)
    if user is None:
        raise NotAuthenticated()
    return user


CurrentUser = Annotated[User, Depends(get_current_user)]


# --- Public API: X-API-Key ------------------------------------------------------------

api_key_header = APIKeyHeader(
    name="X-API-Key",
    auto_error=False,  # we raise our own uniform error instead of FastAPI's default 403
    scheme_name="ApiKey",
    description="A key created in the app under **API keys**. Use the Authorize button to set it once for all requests.",
)


def get_api_key_user(db: DbSession, api_key: Annotated[str | None, Depends(api_key_header)]) -> User:
    """
    Resolve the X-API-Key header to the key's owner, or fail with 401.

    The resulting `User` is the same object the session cookie resolves to,
    so every service downstream is tenant-scoped identically for both paths.
    """
    if not api_key:
        raise InvalidApiKey()
    user = api_key_service.resolve_key(db, api_key)
    if user is None:
        raise InvalidApiKey()
    return user


ApiKeyUser = Annotated[User, Depends(get_api_key_user)]
