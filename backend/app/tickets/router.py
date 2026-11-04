from fastapi import APIRouter, Query, status

from app.core.deps import Cipher, CurrentUser, DbSession
from app.core.errors import (
    JiraAuthFailed,
    JiraNotConnected,
    JiraPermissionDenied,
    JiraUnavailable,
    NotAuthenticated,
    ProjectNotFound,
    ValidationFailed,
    error_responses,
)
from app.tickets import service
from app.tickets.schemas import CreateTicketRequest, TicketResponse, TicketSource

router = APIRouter(prefix="/api/tickets", tags=["Tickets"])


@router.post(
    "",
    status_code=status.HTTP_201_CREATED,
    response_model=TicketResponse,
    summary="Create an NHI finding ticket",
    responses=error_responses(
        NotAuthenticated, JiraNotConnected, ProjectNotFound, ValidationFailed,
        JiraAuthFailed, JiraPermissionDenied, JiraUnavailable,
    ),
)
def create_ticket(payload: CreateTicketRequest, db: DbSession, cipher: Cipher, user: CurrentUser):
    """Creates a real issue in the user's Jira and records it for the recent-tickets view."""
    return service.create_finding_ticket(db, cipher, user, payload, source=TicketSource.ui)


@router.get(
    "",
    response_model=list[TicketResponse],
    summary="Recent tickets created from this app",
    responses=error_responses(NotAuthenticated, ValidationFailed),
)
def list_recent(
    db: DbSession,
    user: CurrentUser,
    project_key: str = Query(min_length=1, max_length=64, examples=["SCRUM"], description="Only tickets in this project."),
    limit: int = Query(default=service.DEFAULT_RECENT_LIMIT, ge=1, le=50),
):
    """Newest first. Includes tickets created through the public API. Served from the local record, so no Jira round-trip."""
    return service.list_recent_tickets(db, user, project_key=project_key, limit=limit)
