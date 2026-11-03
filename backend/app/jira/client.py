"""
A small, explicit client for the Jira Cloud REST API (v3).

Why not the official SDK: every call this app makes to Jira is listed here,
with its error mapping, so a reviewer can see exactly what leaves the system.

Authentication is behind `JiraAuthProvider` so the API-token scheme used by
this POC can be swapped for OAuth without touching the calls themselves.
"""
from __future__ import annotations

import base64
from dataclasses import dataclass
from typing import Any, Protocol

import httpx

from app.core.errors import (
    JiraAuthFailed,
    JiraPermissionDenied,
    JiraUnavailable,
    NotFound,
    ValidationFailed,
)

DEFAULT_TIMEOUT_SECONDS = 15.0
PAGE_SIZE = 50


# --- Authentication ------------------------------------------------------------

class JiraAuthProvider(Protocol):
    """Anything that can authenticate an outgoing request to Jira."""

    def apply(self, request: httpx.Request) -> None: ...


class ApiTokenAuth:
    """Atlassian API token: HTTP Basic auth with `email:token`."""

    def __init__(self, email: str, api_token: str):
        credentials = f"{email}:{api_token}".encode("utf-8")
        self._header = "Basic " + base64.b64encode(credentials).decode("ascii")

    def apply(self, request: httpx.Request) -> None:
        request.headers["Authorization"] = self._header


# --- Data returned to the rest of the app ----------------------------------------

@dataclass(frozen=True)
class JiraUser:
    account_id: str
    display_name: str
    email: str | None


@dataclass(frozen=True)
class JiraProject:
    id: str
    key: str
    name: str


@dataclass(frozen=True)
class JiraIssueType:
    id: str
    name: str
    description: str
    subtask: bool


@dataclass(frozen=True)
class JiraIssueCreated:
    id: str
    key: str
    url: str


# --- Client -----------------------------------------------------------------------

class JiraClient:
    def __init__(
        self,
        site_url: str,
        auth: JiraAuthProvider,
        *,
        timeout: float = DEFAULT_TIMEOUT_SECONDS,
        transport: httpx.BaseTransport | None = None,  # tests inject a fake Jira here
    ):
        self.site_url = site_url.rstrip("/")
        self._auth = auth
        self._http = httpx.Client(
            base_url=f"{self.site_url}/rest/api/3",
            timeout=timeout,
            transport=transport,
            headers={"Accept": "application/json"},
        )

    # -- calls ---------------------------------------------------------------

    def get_myself(self) -> JiraUser:
        """Who the credentials belong to. Used to verify a connection before saving it."""
        data = self._request("GET", "/myself")
        return JiraUser(
            account_id=data["accountId"],
            display_name=data.get("displayName", ""),
            email=data.get("emailAddress"),
        )

    def list_projects(self) -> list[JiraProject]:
        """All projects visible to the user, following Jira's pagination."""
        projects: list[JiraProject] = []
        start_at = 0
        while True:
            data = self._request(
                "GET", "/project/search",
                params={"startAt": start_at, "maxResults": PAGE_SIZE, "orderBy": "name"},
            )
            projects.extend(
                JiraProject(id=str(p["id"]), key=p["key"], name=p["name"]) for p in data.get("values", [])
            )
            if data.get("isLast", True) or not data.get("values"):
                return projects
            start_at += len(data["values"])

    def list_issue_types(self, project_key: str) -> list[JiraIssueType]:
        """Issue types the user may create in a project. Sub-tasks are excluded (they need a parent)."""
        data = self._request(
            "GET", f"/issue/createmeta/{project_key}/issuetypes",
            params={"maxResults": PAGE_SIZE},
            not_found=f"project {project_key}",
        )
        # Jira has used both keys for this payload across versions.
        raw = data.get("issueTypes") or data.get("values") or []
        return [
            JiraIssueType(
                id=str(t["id"]), name=t["name"], description=t.get("description", ""), subtask=bool(t.get("subtask"))
            )
            for t in raw
            if not t.get("subtask")
        ]

    def create_issue(
        self,
        *,
        project_key: str,
        issue_type_name: str,
        summary: str,
        description_adf: dict[str, Any],
        labels: list[str],
    ) -> JiraIssueCreated:
        payload = {
            "fields": {
                "project": {"key": project_key},
                "issuetype": {"name": issue_type_name},
                "summary": summary,
                "description": description_adf,
                "labels": labels,
            }
        }
        data = self._request("POST", "/issue", json=payload)
        key = data["key"]
        return JiraIssueCreated(id=str(data["id"]), key=key, url=f"{self.site_url}/browse/{key}")

    # -- plumbing -------------------------------------------------------------

    def _request(self, method: str, path: str, *, not_found: str | None = None, **kwargs) -> dict[str, Any]:
        """Send one request and translate every failure into a typed AppError."""
        request = self._http.build_request(method, path, **kwargs)
        self._auth.apply(request)
        try:
            response = self._http.send(request)
        except httpx.TimeoutException as exc:
            raise JiraUnavailable("Jira did not respond in time. Please try again.") from exc
        except httpx.HTTPError as exc:
            raise JiraUnavailable(
                "Could not reach Jira. Check the site URL and your network connection.",
                details={"site_url": self.site_url},
            ) from exc

        if response.is_success:
            return response.json() if response.content else {}

        jira_messages = _extract_messages(response)
        details = {"jira_status": response.status_code, "jira_messages": jira_messages}

        if response.status_code == 401:
            raise JiraAuthFailed(details=details)
        if response.status_code == 403:
            raise JiraPermissionDenied(details=details)
        if response.status_code == 404:
            what = not_found or "resource"
            raise NotFound(f"Jira could not find the {what}.", details=details)
        if response.status_code == 400:
            raise ValidationFailed(
                "Jira rejected the request: " + ("; ".join(jira_messages) or "invalid input."),
                details=details,
            )
        raise JiraUnavailable(details=details)


def _extract_messages(response: httpx.Response) -> list[str]:
    """Jira reports errors as {"errorMessages": [...], "errors": {"field": "msg"}}."""
    try:
        body = response.json()
    except ValueError:
        return []
    messages = list(body.get("errorMessages", []))
    messages.extend(f"{field}: {msg}" for field, msg in body.get("errors", {}).items())
    return messages
