"""
Application errors and the handlers that turn them into HTTP responses.

Services raise one of the typed errors below. A single set of handlers,
registered in main.py, maps each to a status code and renders the same JSON
shape for every error the API can produce:

    {"error": {"code": "...", "message": "...", "details": {...}}}

`code` is stable and meant for machines (the UI and external callers branch
on it). `message` is meant for people and must say what to do next.
"""
from __future__ import annotations

import logging
from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

log = logging.getLogger(__name__)


class AppError(Exception):
    status_code: int = 500
    code: str = "internal_error"
    message: str = "Something went wrong on our side. Please try again."

    def __init__(self, message: str | None = None, *, details: dict[str, Any] | None = None):
        super().__init__(message or self.message)
        if message is not None:
            self.message = message
        self.details = details or {}

    def to_body(self) -> dict[str, Any]:
        return {"error": {"code": self.code, "message": self.message, "details": self.details}}


# --- Authentication / authorization ---------------------------------------

class NotAuthenticated(AppError):
    status_code = 401
    code = "not_authenticated"
    message = "You need to log in to do this."


class InvalidCredentials(AppError):
    status_code = 401
    code = "invalid_credentials"
    # Deliberately vague: do not reveal whether the email exists.
    message = "Invalid email or password."


class InvalidApiKey(AppError):
    status_code = 401
    code = "invalid_api_key"
    message = "The API key is missing, invalid, or has been revoked. Send it in the X-API-Key header."


# --- Resource state ----------------------------------------------------------

class EmailAlreadyRegistered(AppError):
    status_code = 409
    code = "email_already_registered"
    message = "An account with this email already exists. Try logging in instead."


class NotFound(AppError):
    status_code = 404
    code = "not_found"
    message = "The requested resource does not exist."


class ValidationFailed(AppError):
    status_code = 422
    code = "validation_failed"
    message = "Some fields are missing or invalid."


# --- Jira ------------------------------------------------------------------

class JiraNotConnected(AppError):
    status_code = 409
    code = "jira_not_connected"
    message = "No Jira workspace is connected to this account. Connect one first."


class JiraAuthFailed(AppError):
    status_code = 400
    code = "jira_auth_failed"
    message = "Jira rejected the credentials. Check the site URL, email and API token."


class JiraPermissionDenied(AppError):
    status_code = 403
    code = "jira_permission_denied"
    message = "Your Jira account does not have permission for this action in the selected project."


class ProjectNotFound(AppError):
    status_code = 404
    code = "project_not_found"
    message = "The selected Jira project does not exist or is not visible to your Jira account."


class JiraUnavailable(AppError):
    status_code = 502
    code = "jira_unavailable"
    message = "Jira could not be reached or returned an unexpected error. Please try again shortly."


# --- Handlers ----------------------------------------------------------------

def register_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(AppError)
    async def _app_error(_request: Request, exc: AppError) -> JSONResponse:
        return JSONResponse(status_code=exc.status_code, content=exc.to_body())

    @app.exception_handler(RequestValidationError)
    async def _validation_error(_request: Request, exc: RequestValidationError) -> JSONResponse:
        # Reshape FastAPI's native 422 into our uniform error body, keeping
        # the per-field information so a client can highlight the right input.
        fields = [
            {"field": ".".join(str(p) for p in err["loc"] if p not in ("body", "query", "path")),
             "problem": err["msg"]}
            for err in exc.errors()
        ]
        body = ValidationFailed(details={"fields": fields}).to_body()
        return JSONResponse(status_code=422, content=body)

    @app.exception_handler(Exception)
    async def _unexpected(_request: Request, exc: Exception) -> JSONResponse:
        # Log the real cause for operators; never leak it to the client.
        log.exception("Unhandled error: %s", exc)
        return JSONResponse(status_code=500, content=AppError().to_body())
