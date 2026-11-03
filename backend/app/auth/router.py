from fastapi import APIRouter, Request, Response, status

from app.auth import service
from app.auth.schemas import LoginRequest, RegisterRequest, UserResponse
from app.config import Settings
from app.core.deps import AppSettings, CurrentUser, DbSession
from app.models import User

router = APIRouter(prefix="/api/auth", tags=["Auth"])


def _to_response(user: User) -> UserResponse:
    return UserResponse(
        id=user.id,
        email=user.email,
        created_at=user.created_at,
        jira_connected=user.jira_connection is not None,
    )


def _set_session_cookie(response: Response, settings: Settings, token: str) -> None:
    response.set_cookie(
        key=settings.session_cookie_name,
        value=token,
        max_age=settings.session_ttl_hours * 3600,
        httponly=True,                   # not readable from JavaScript
        samesite="lax",                  # not sent on cross-site POSTs
        secure=settings.cookie_secure,   # HTTPS only, when enabled
        path="/",
    )


def _clear_session_cookie(response: Response, settings: Settings) -> None:
    response.delete_cookie(key=settings.session_cookie_name, path="/")


@router.post(
    "/register",
    status_code=status.HTTP_201_CREATED,
    response_model=UserResponse,
    summary="Create an account",
    responses={409: {"description": "Email already registered"}},
)
def register(payload: RegisterRequest, response: Response, db: DbSession, settings: AppSettings):
    """Create an account and log in immediately (sets the session cookie)."""
    user = service.register(db, email=payload.email, password=payload.password)
    _set_session_cookie(response, settings, service.open_session(db, user))
    return _to_response(user)


@router.post(
    "/login",
    response_model=UserResponse,
    summary="Log in",
    responses={401: {"description": "Invalid email or password"}},
)
def login(payload: LoginRequest, response: Response, db: DbSession, settings: AppSettings):
    """Verify credentials and set the session cookie."""
    user, token = service.login(db, email=payload.email, password=payload.password)
    _set_session_cookie(response, settings, token)
    return _to_response(user)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT, summary="Log out")
def logout(request: Request, response: Response, db: DbSession, settings: AppSettings):
    """End the session server-side and clear the cookie. Safe to call when not logged in."""
    token = request.cookies.get(settings.session_cookie_name)
    if token:
        service.logout(db, token)
    _clear_session_cookie(response, settings)


@router.get("/me", response_model=UserResponse, summary="Current user")
def me(user: CurrentUser):
    return _to_response(user)
