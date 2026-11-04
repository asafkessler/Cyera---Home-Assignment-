"""
Public API v1, for external systems.

Authentication: `X-API-Key` header. The key identifies a user, and everything
happens in that user's connected Jira workspace. The ticket-creation logic is
the same service the web UI uses; only the authentication differs.
"""
from fastapi import APIRouter, status

from app.core.deps import ApiKeyUser, Cipher, DbSession
from app.core.errors import (
    InvalidApiKey,
    JiraAuthFailed,
    JiraNotConnected,
    JiraPermissionDenied,
    JiraUnavailable,
    ProjectNotFound,
    ValidationFailed,
    error_responses,
)
from app.jira import service as jira_service
from app.public_api.v1.schemas import FindingCreated, NhiFinding, Project
from app.tickets import service as tickets_service
from app.tickets.schemas import TicketSource

router = APIRouter(prefix="/api/v1", tags=["Public API v1"])


@router.post(
    "/findings",
    status_code=status.HTTP_201_CREATED,
    response_model=FindingCreated,
    summary="Report an NHI finding as a Jira ticket",
    responses=error_responses(
        InvalidApiKey, JiraNotConnected, ProjectNotFound, ValidationFailed,
        JiraAuthFailed, JiraPermissionDenied, JiraUnavailable,
    ),
)
def create_finding(finding: NhiFinding, db: DbSession, cipher: Cipher, user: ApiKeyUser):
    """
    Creates a ticket in the Jira project named by `project_key`, in the
    workspace connected by the key's owner. The ticket is labelled
    `identityhub` / `nhi-finding` and appears in the app's recent-tickets view.

    **Status codes**

    | Code | Meaning |
    |---|---|
    | 201 | Ticket created; the body has the issue key and URL |
    | 401 | Missing, invalid or revoked API key |
    | 404 | `project_key` does not exist or is not visible to the key owner |
    | 409 | The key owner has not connected a Jira workspace |
    | 422 | A field is missing or invalid, or `issue_type` is not available in the project (`details.fields` names it) |
    | 502 | Jira could not be reached or returned an unexpected error |
    """
    return tickets_service.create_finding_ticket(db, cipher, user, finding, source=TicketSource.api)


@router.get(
    "/projects",
    response_model=list[Project],
    summary="List projects a finding can be reported to",
    responses=error_responses(InvalidApiKey, JiraNotConnected, JiraAuthFailed, JiraUnavailable),
)
def list_projects(db: DbSession, cipher: Cipher, user: ApiKeyUser):
    """Lets an external system discover valid `project_key` values before reporting findings."""
    return jira_service.list_projects(db, cipher, user)
