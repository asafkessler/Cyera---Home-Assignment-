"""
Jira connection use cases: connect (verify + store), disconnect, status, and
building an authenticated client for a user.

The decrypted API token exists only inside `client_for_user`, for the
duration of one request, and is never returned anywhere.
"""
from sqlalchemy.orm import Session as DbSession

from app.core.errors import JiraNotConnected
from app.core.security import CredentialCipher
from app.jira import repository
from app.jira.client import ApiTokenAuth, JiraClient, JiraIssueType, JiraProject
from app.models import JiraConnection, User


def connect(
    db: DbSession,
    cipher: CredentialCipher,
    user: User,
    *,
    site_url: str,
    email: str,
    api_token: str,
) -> JiraConnection:
    """
    Verify the credentials against Jira, then store them encrypted.

    Verifying first means a typo in the token is reported now, with a specific
    message, rather than later when the user tries to create a ticket.
    """
    client = JiraClient(site_url, ApiTokenAuth(email, api_token))
    me = client.get_myself()  # raises JiraAuthFailed / JiraUnavailable
    return repository.upsert_connection(
        db,
        user.id,
        site_url=site_url,
        email=email,
        api_token_encrypted=cipher.encrypt(api_token),
        jira_account_id=me.account_id,
        display_name=me.display_name,
    )


def disconnect(db: DbSession, user: User) -> None:
    repository.delete_connection(db, user.id)


def get_status(db: DbSession, user: User) -> JiraConnection | None:
    return repository.get_connection(db, user.id)


def client_for_user(db: DbSession, cipher: CredentialCipher, user: User) -> JiraClient:
    """An authenticated client for this user's workspace, or JiraNotConnected."""
    connection = repository.get_connection(db, user.id)
    if connection is None:
        raise JiraNotConnected()
    api_token = cipher.decrypt(connection.api_token_encrypted)
    return JiraClient(connection.site_url, ApiTokenAuth(connection.email, api_token))


def list_projects(db: DbSession, cipher: CredentialCipher, user: User) -> list[JiraProject]:
    return client_for_user(db, cipher, user).list_projects()


def list_issue_types(db: DbSession, cipher: CredentialCipher, user: User, project_key: str) -> list[JiraIssueType]:
    return client_for_user(db, cipher, user).list_issue_types(project_key)
