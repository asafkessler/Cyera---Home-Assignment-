"""
The external contract. Kept separate from the internal schemas so the public
API can evolve (or stay frozen) independently of what the UI uses.
"""
from datetime import datetime

from pydantic import BaseModel, Field

from app.tickets.schemas import CreateTicketRequest, TicketSource


class NhiFinding(CreateTicketRequest):
    """An NHI finding reported by an external system (scanner, CI/CD pipeline, automation)."""

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "project_key": "SCRUM",
                    "summary": "Stale service account: svc-deploy-prod",
                    "description": "No authentication events in 94 days.\nOwner team: platform.\nRecommend disabling the account and rotating its key.",
                    "severity": "high",
                    "identity_type": "service_account",
                    "issue_type": "Task",
                }
            ]
        }
    }


class FindingCreated(BaseModel):
    issue_key: str = Field(description="The Jira issue key.", examples=["SCRUM-12"])
    issue_url: str = Field(description="Direct link to the issue in Jira.", examples=["https://your-team.atlassian.net/browse/SCRUM-12"])
    project_key: str = Field(examples=["SCRUM"])
    summary: str
    source: TicketSource = Field(description="Always `api` for tickets created through this endpoint.")
    created_at: datetime

    model_config = {"from_attributes": True}


class Project(BaseModel):
    id: str
    key: str = Field(examples=["SCRUM"])
    name: str = Field(examples=["NHI Findings"])
