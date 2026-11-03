from fastapi import APIRouter, Path, status

from app.core.deps import Cipher, CurrentUser, DbSession
from app.jira import service
from app.jira.schemas import ConnectJiraRequest, IssueTypeResponse, JiraConnectionResponse, ProjectResponse
from app.models import JiraConnection

router = APIRouter(prefix="/api/jira", tags=["Jira"])

_NOT_CONNECTED = {409: {"description": "No Jira workspace connected"}}
_JIRA_ERRORS = {
    400: {"description": "Jira rejected the credentials (jira_auth_failed)"},
    502: {"description": "Jira unreachable or returned an unexpected error"},
}


def _status(connection: JiraConnection | None) -> JiraConnectionResponse:
    if connection is None:
        return JiraConnectionResponse(connected=False)
    return JiraConnectionResponse(
        connected=True,
        site_url=connection.site_url,
        email=connection.email,
        display_name=connection.display_name,
        connected_at=connection.connected_at,
        last_verified_at=connection.last_verified_at,
    )


@router.get("/connection", response_model=JiraConnectionResponse, summary="Connection status")
def get_connection(db: DbSession, user: CurrentUser):
    """Whether a Jira workspace is connected. The API token is never returned."""
    return _status(service.get_status(db, user))


@router.put(
    "/connection",
    response_model=JiraConnectionResponse,
    summary="Connect (or replace) a Jira workspace",
    responses=_JIRA_ERRORS,
)
def connect(payload: ConnectJiraRequest, db: DbSession, cipher: Cipher, user: CurrentUser):
    """Verifies the credentials against Jira before saving them, encrypted, for this account."""
    connection = service.connect(
        db, cipher, user, site_url=payload.site_url, email=payload.email, api_token=payload.api_token
    )
    return _status(connection)


@router.delete("/connection", status_code=status.HTTP_204_NO_CONTENT, summary="Disconnect Jira")
def disconnect(db: DbSession, user: CurrentUser):
    """Deletes the stored credentials. Tickets already recorded are kept."""
    service.disconnect(db, user)


@router.get(
    "/projects",
    response_model=list[ProjectResponse],
    summary="Projects in the connected workspace",
    responses={**_NOT_CONNECTED, **_JIRA_ERRORS},
)
def list_projects(db: DbSession, cipher: Cipher, user: CurrentUser):
    return service.list_projects(db, cipher, user)


@router.get(
    "/projects/{project_key}/issue-types",
    response_model=list[IssueTypeResponse],
    summary="Issue types available in a project",
    responses={**_NOT_CONNECTED, **_JIRA_ERRORS, 404: {"description": "Project not found"}},
)
def list_issue_types(
    db: DbSession,
    cipher: Cipher,
    user: CurrentUser,
    project_key: str = Path(examples=["SCRUM"], pattern=r"^[A-Za-z][A-Za-z0-9_]*$"),
):
    return service.list_issue_types(db, cipher, user, project_key.upper())
