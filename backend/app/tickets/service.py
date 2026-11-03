"""
The ticket use cases.

`create_finding_ticket` is the single entry point for creating a ticket. The
UI router and the public API router both call it, differing only in how the
caller was authenticated. Everything that must be true of every ticket
(validated input, the `identityhub` label, the local record, tenant scoping)
is therefore enforced here, once.
"""
from sqlalchemy.orm import Session as DbSession

from app.core.errors import NotFound, ProjectNotFound, ValidationFailed
from app.core.security import CredentialCipher
from app.jira import service as jira_service
from app.models import Ticket, User, utcnow
from app.tickets import repository
from app.tickets.description import build_description
from app.tickets.schemas import CreateTicketRequest, TicketSource

DEFAULT_RECENT_LIMIT = 10
LABELS = ["identityhub", "nhi-finding"]


def create_finding_ticket(
    db: DbSession,
    cipher: CredentialCipher,
    user: User,
    payload: CreateTicketRequest,
    *,
    source: TicketSource,
) -> Ticket:
    client = jira_service.client_for_user(db, cipher, user)  # JiraNotConnected if none
    reported_at = utcnow()
    description = build_description(
        description=payload.description,
        severity=payload.severity,
        identity_type=payload.identity_type,
        source=source,
        reported_at=reported_at,
    )
    try:
        created = client.create_issue(
            project_key=payload.project_key,
            issue_type_name=payload.issue_type,
            summary=payload.summary,
            description_adf=description,
            labels=LABELS,
        )
    except ValidationFailed as exc:
        raise _refine_jira_validation_error(exc, payload) from exc
    except NotFound as exc:
        raise ProjectNotFound(details=exc.details) from exc

    return repository.insert(
        db,
        user_id=user.id,
        project_key=payload.project_key,
        issue_key=created.key,
        issue_id=created.id,
        summary=payload.summary,
        issue_url=created.url,
        source=source.value,
    )


def list_recent_tickets(db: DbSession, user: User, *, project_key: str, limit: int = DEFAULT_RECENT_LIMIT) -> list[Ticket]:
    return repository.list_recent(db, user_id=user.id, project_key=project_key.upper(), limit=limit)


def _refine_jira_validation_error(exc: ValidationFailed, payload: CreateTicketRequest) -> Exception:
    """
    Jira answers 400 for several different problems. Turn the two common ones
    into errors a user can act on; pass anything else through with Jira's text.
    """
    messages = " ".join(exc.details.get("jira_messages", [])).lower()
    if "project" in messages and ("valid" in messages or "exist" in messages):
        return ProjectNotFound(details=exc.details)
    if "issuetype" in messages or "issue type" in messages:
        return ValidationFailed(
            f'Issue type "{payload.issue_type}" is not available in project {payload.project_key}. '
            "Pick one of the project's issue types.",
            details={**exc.details, "fields": [{"field": "issue_type", "problem": "not available in this project"}]},
        )
    return exc
