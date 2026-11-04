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
from pydantic import BaseModel, Field

log = logging.getLogger(__name__)


class ErrorBody(BaseModel):
    code: str = Field(description="Stable, machine-readable error code.", examples=["jira_not_connected"])
    message: str = Field(description="Human-readable explanation and what to do next.")
    details: dict[str, Any] = Field(default_factory=dict, description="Optional structured context (e.g. offending fields).")


class ErrorResponse(BaseModel):
    """The one shape every error response has."""

    error: ErrorBody


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


# --- OpenAPI documentation helper ----------------------------------------------

def error_responses(*errors: type[AppError], **extra_examples: dict[str, Any]) -> dict[int, dict[str, Any]]:
    """
    Build the `responses=` mapping for a route from the AppError classes it can
    raise, so the API docs show, for every endpoint, exactly which status codes
    and error codes to expect, with a realistic example body for each.

    Several errors can share a status code (e.g. 404 for both a missing project
    and a missing API key); they are merged into one entry with named examples.
    """
    responses: dict[int, dict[str, Any]] = {}
    for err in errors:
        example = err().to_body()
        entry = responses.setdefault(
            err.status_code,
            {"model": ErrorResponse, "description": "", "content": {"application/json": {"examples": {}}}},
        )
        entry["content"]["application/json"]["examples"][err.code] = {
            "summary": err.code,
            "value": example,
        }
        entry["description"] = ", ".join(f"`{code}`" for code in entry["content"]["application/json"]["examples"])
    return responses


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
