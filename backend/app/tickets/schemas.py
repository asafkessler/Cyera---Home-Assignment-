from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field, field_validator

JIRA_SUMMARY_MAX = 255           # Jira's hard limit for the summary field
DESCRIPTION_MAX = 30_000         # generous; Jira allows far more, but keeps payloads sane


class Severity(str, Enum):
    low = "low"
    medium = "medium"
    high = "high"
    critical = "critical"


class IdentityType(str, Enum):
    service_account = "service_account"
    api_key = "api_key"
    service_principal = "service_principal"
    other = "other"


class TicketSource(str, Enum):
    ui = "ui"
    api = "api"


class CreateTicketRequest(BaseModel):
    """An NHI finding to report as a Jira ticket. Shared by the UI and the public API."""

    project_key: str = Field(
        min_length=1, max_length=64, pattern=r"^[A-Za-z][A-Za-z0-9_]*$",
        description="Key of the Jira project to create the ticket in.",
        examples=["SCRUM"],
    )
    summary: str = Field(
        min_length=3, max_length=JIRA_SUMMARY_MAX,
        description="Ticket title. One line.",
        examples=["Stale service account: svc-deploy-prod"],
    )
    description: str = Field(
        min_length=1, max_length=DESCRIPTION_MAX,
        description="Details of the finding: what was observed, where, and what should be done.",
        examples=["No authentication events in 94 days. Owner team: platform. Recommend disabling the account and rotating its key."],
    )
    severity: Severity | None = Field(
        default=None, description="How urgent the finding is.", examples=["high"],
    )
    identity_type: IdentityType | None = Field(
        default=None, description="What kind of non-human identity the finding is about.", examples=["service_account"],
    )
    issue_type: str = Field(
        default="Task", min_length=1, max_length=100,
        description="Jira issue type name. Must exist in the project; see the project's issue types.",
        examples=["Task"],
    )

    @field_validator("project_key")
    @classmethod
    def _upper(cls, value: str) -> str:
        return value.upper()

    @field_validator("summary", "description")
    @classmethod
    def _strip(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("must not be blank")
        return stripped


class TicketResponse(BaseModel):
    id: int
    issue_key: str = Field(examples=["SCRUM-12"])
    issue_url: str = Field(examples=["https://your-team.atlassian.net/browse/SCRUM-12"])
    summary: str
    project_key: str
    source: TicketSource = Field(description="Whether the ticket was created from the web form or the public API.")
    created_at: datetime

    model_config = {"from_attributes": True}
