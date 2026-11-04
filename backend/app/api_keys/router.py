from fastapi import APIRouter, status

from app.api_keys import service
from app.api_keys.schemas import ApiKeyCreatedResponse, ApiKeyResponse, CreateApiKeyRequest
from app.core.deps import CurrentUser, DbSession
from app.core.errors import NotAuthenticated, NotFound, error_responses

router = APIRouter(prefix="/api/keys", tags=["API keys"])


@router.get(
    "",
    response_model=list[ApiKeyResponse],
    summary="List my API keys",
    responses=error_responses(NotAuthenticated),
)
def list_keys(db: DbSession, user: CurrentUser):
    """Newest first. Revoked keys are included with their `revoked_at` set."""
    return service.list_keys(db, user)


@router.post(
    "",
    status_code=status.HTTP_201_CREATED,
    response_model=ApiKeyCreatedResponse,
    summary="Create an API key",
    responses=error_responses(NotAuthenticated),
)
def create_key(payload: CreateApiKeyRequest, db: DbSession, user: CurrentUser):
    """
    Creates a key for the public API. The full key is returned **only here**;
    afterwards only its prefix is visible. Requests made with it act as you
    and create tickets in your connected Jira workspace.
    """
    api_key, raw_key = service.create_key(db, user, name=payload.name)
    return ApiKeyCreatedResponse(
        id=api_key.id,
        name=api_key.name,
        key_prefix=api_key.key_prefix,
        created_at=api_key.created_at,
        last_used_at=api_key.last_used_at,
        revoked_at=api_key.revoked_at,
        key=raw_key,
    )


@router.delete(
    "/{key_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Revoke an API key",
    responses=error_responses(NotAuthenticated, NotFound),
)
def revoke_key(key_id: int, db: DbSession, user: CurrentUser):
    """Revocation is immediate and permanent. Already-revoked keys return 204 as well."""
    service.revoke_key(db, user, key_id)
