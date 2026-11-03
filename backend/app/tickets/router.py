from fastapi import APIRouter, Query, status

from app.core.deps import Cipher, CurrentUser, DbSession
from app.tickets import service
from app.tickets.schemas import CreateTicketRequest, TicketResponse, TicketSource

router = APIRouter(prefix="/api/tickets", tags=["Tickets"])


@router.post(
    "",
    status_code=status.HTTP_201_CREATED,
    response_model=TicketResponse,
    summary="Create an NHI finding ticket",
    responses={
        404: {"description": "Project not found in the connected workspace"},
        409: {"description": "No Jira workspace connected"},
        422: {"description": "Invalid input, or issue type not available in the project"},
        502: {"description": "Jira unreachable or returned an unexpected error"},
    },
)
def create_ticket(payload: CreateTicketRequest, db: DbSession, cipher: Cipher, user: CurrentUser):
    """Creates a real issue in the user's Jira and records it for the recent-tickets view."""
    return service.create_finding_ticket(db, cipher, user, payload, source=TicketSource.ui)


@router.get(
    "",
    response_model=list[TicketResponse],
    summary="Recent tickets created from this app",
)
def list_recent(
    db: DbSession,
    user: CurrentUser,
    project_key: str = Query(min_length=1, max_length=64, examples=["SCRUM"], description="Only tickets in this project."),
    limit: int = Query(default=service.DEFAULT_RECENT_LIMIT, ge=1, le=50),
):
    """Newest first. Includes tickets created through the public API. Served from the local record, so no Jira round-trip."""
    return service.list_recent_tickets(db, user, project_key=project_key, limit=limit)
