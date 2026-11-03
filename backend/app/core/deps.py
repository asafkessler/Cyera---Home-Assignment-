"""
FastAPI dependencies shared by routers.

A dependency is a function FastAPI calls to produce a value for a route
parameter. Centralising them here means a route declares *what* it needs
(a database session, the logged-in user) and never *how* to get it.
"""
from typing import Annotated

from fastapi import Depends, Request
from sqlalchemy.orm import Session

from app.auth import service as auth_service
from app.config import Settings, get_settings
from app.core.errors import NotAuthenticated
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
