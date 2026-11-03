"""
An in-process stand-in for Jira Cloud, plugged into httpx as a transport.

It implements only the endpoints the app calls, with realistic payloads, and
lets a test decide which credentials are valid and which projects exist.
Used by the API tests so they run without network access or a Jira account.
"""
from __future__ import annotations

import base64
import json
from dataclasses import dataclass, field

import httpx

SITE_URL = "https://fake.atlassian.net"
VALID_EMAIL = "owner@example.com"
VALID_TOKEN = "valid-token"


@dataclass
class FakeJira:
    projects: list[dict] = field(default_factory=lambda: [
        {"id": "10000", "key": "SCRUM", "name": "NHI Findings"},
        {"id": "10001", "key": "OPS", "name": "Operations"},
    ])
    issue_types: list[dict] = field(default_factory=lambda: [
        {"id": "10001", "name": "Task", "description": "A small piece of work.", "subtask": False},
        {"id": "10002", "name": "Bug", "description": "A problem.", "subtask": False},
        {"id": "10003", "name": "Sub-task", "description": "", "subtask": True},
    ])
    page_size: int = 1                     # tiny pages so pagination is exercised
    created: list[dict] = field(default_factory=list)
    fail_with: Exception | None = None     # simulate network failures
    next_issue_number: int = 1
    requests: list[httpx.Request] = field(default_factory=list)

    # -- httpx transport ---------------------------------------------------------

    def transport(self) -> httpx.MockTransport:
        return httpx.MockTransport(self.handle)

    def handle(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        if self.fail_with is not None:
            raise self.fail_with
        if not self._authorised(request):
            return _json(401, {"errorMessages": ["Client must be authenticated to access this resource."]})

        path = request.url.path.removeprefix("/rest/api/3")
        if request.method == "GET" and path == "/myself":
            return _json(200, {"accountId": "acc-123", "displayName": "Asaf Kessler", "emailAddress": VALID_EMAIL})

        if request.method == "GET" and path == "/project/search":
            start = int(request.url.params.get("startAt", 0))
            page = self.projects[start:start + self.page_size]
            return _json(200, {
                "values": page,
                "startAt": start,
                "maxResults": self.page_size,
                "total": len(self.projects),
                "isLast": start + len(page) >= len(self.projects),
            })

        if request.method == "GET" and path.startswith("/issue/createmeta/") and path.endswith("/issuetypes"):
            key = path.split("/")[3]
            if not self._project(key):
                return _json(404, {"errorMessages": ["The project does not exist or you do not have permission."]})
            return _json(200, {"issueTypes": self.issue_types, "startAt": 0, "maxResults": 50, "total": 3})

        if request.method == "POST" and path == "/issue":
            fields = json.loads(request.content)["fields"]
            key = fields["project"]["key"]
            if not self._project(key):
                return _json(400, {"errorMessages": [], "errors": {"project": "Specify a valid project ID or key"}})
            if fields["issuetype"]["name"] not in {t["name"] for t in self.issue_types}:
                return _json(400, {"errorMessages": [], "errors": {"issuetype": "Specify a valid issue type"}})
            issue_key = f"{key}-{self.next_issue_number}"
            self.next_issue_number += 1
            self.created.append({"key": issue_key, "fields": fields})
            return _json(201, {"id": str(20000 + len(self.created)), "key": issue_key, "self": f"{SITE_URL}/rest/api/3/issue/{issue_key}"})

        return _json(404, {"errorMessages": ["Unknown endpoint in FakeJira: " + path]})

    # -- helpers ------------------------------------------------------------------

    def _authorised(self, request: httpx.Request) -> bool:
        header = request.headers.get("Authorization", "")
        if not header.startswith("Basic "):
            return False
        email, _, token = base64.b64decode(header[6:]).decode().partition(":")
        return email == VALID_EMAIL and token == VALID_TOKEN

    def _project(self, key: str) -> dict | None:
        return next((p for p in self.projects if p["key"] == key), None)


def _json(status: int, body: dict) -> httpx.Response:
    return httpx.Response(status, json=body)
