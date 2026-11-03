from datetime import datetime

from pydantic import BaseModel, EmailStr, Field, field_validator


class ConnectJiraRequest(BaseModel):
    site_url: str = Field(
        description="Your Jira Cloud site, e.g. https://your-team.atlassian.net",
        examples=["https://your-team.atlassian.net"],
    )
    email: EmailStr = Field(description="The Atlassian account email the API token belongs to.")
    api_token: str = Field(
        min_length=1,
        description="An Atlassian API token created at https://id.atlassian.com/manage-profile/security/api-tokens",
    )

    @field_validator("site_url")
    @classmethod
    def _normalise_site_url(cls, value: str) -> str:
        """Accept 'team.atlassian.net', 'https://team.atlassian.net/', etc. Always store https without a trailing slash."""
        value = value.strip().rstrip("/")
        if "://" not in value:
            value = f"https://{value}"
        if not value.startswith("https://"):
            raise ValueError("site_url must use https")
        host = value.removeprefix("https://")
        if not host or "/" in host or " " in host or "." not in host:
            raise ValueError("site_url must be a hostname like https://your-team.atlassian.net")
        return value


class JiraConnectionResponse(BaseModel):
    connected: bool
    site_url: str | None = None
    email: str | None = None
    display_name: str | None = None
    connected_at: datetime | None = None
    last_verified_at: datetime | None = None


class ProjectResponse(BaseModel):
    id: str
    key: str = Field(examples=["SCRUM"])
    name: str = Field(examples=["NHI Findings"])


class IssueTypeResponse(BaseModel):
    id: str
    name: str = Field(examples=["Task"])
    description: str = ""
