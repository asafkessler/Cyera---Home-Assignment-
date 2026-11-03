"""
Render an NHI finding as a Jira description.

Jira Cloud's v3 API takes descriptions in Atlassian Document Format (ADF), a
JSON tree, not plain text. This module is the only place that knows ADF.

The structured fields (severity, identity type, source) go into a short
bullet list at the top, so they are visible at a glance in any Jira project
without custom fields. The free-text description follows as paragraphs.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any

from app.tickets.schemas import IdentityType, Severity, TicketSource

_IDENTITY_TYPE_LABELS = {
    IdentityType.service_account: "Service account",
    IdentityType.api_key: "API key",
    IdentityType.service_principal: "Service principal",
    IdentityType.other: "Other",
}
_SOURCE_LABELS = {
    TicketSource.ui: "IdentityHub web app",
    TicketSource.api: "IdentityHub API (automated)",
}


def build_description(
    *,
    description: str,
    severity: Severity | None,
    identity_type: IdentityType | None,
    source: TicketSource,
    reported_at: datetime,
) -> dict[str, Any]:
    facts: list[tuple[str, str]] = []
    if severity is not None:
        facts.append(("Severity", severity.value.capitalize()))
    if identity_type is not None:
        facts.append(("Identity type", _IDENTITY_TYPE_LABELS[identity_type]))
    facts.append(("Reported via", _SOURCE_LABELS[source]))
    facts.append(("Reported at", reported_at.strftime("%Y-%m-%d %H:%M UTC")))

    content: list[dict[str, Any]] = [
        _heading("NHI finding", level=3),
        _bullet_list([_paragraph(_strong(f"{label}: "), _text(value)) for label, value in facts]),
        _heading("Details", level=3),
    ]
    content.extend(_paragraph(_text(line)) for line in _split_paragraphs(description))
    return {"type": "doc", "version": 1, "content": content}


# --- ADF building blocks ------------------------------------------------------------

def _split_paragraphs(text: str) -> list[str]:
    paragraphs = [p.strip() for p in text.replace("\r\n", "\n").split("\n")]
    return [p for p in paragraphs if p] or [text]


def _text(value: str) -> dict[str, Any]:
    return {"type": "text", "text": value}


def _strong(value: str) -> dict[str, Any]:
    return {"type": "text", "text": value, "marks": [{"type": "strong"}]}


def _paragraph(*inline: dict[str, Any]) -> dict[str, Any]:
    return {"type": "paragraph", "content": list(inline)}


def _heading(value: str, *, level: int) -> dict[str, Any]:
    return {"type": "heading", "attrs": {"level": level}, "content": [_text(value)]}


def _bullet_list(items: list[dict[str, Any]]) -> dict[str, Any]:
    return {"type": "bulletList", "content": [{"type": "listItem", "content": [item]} for item in items]}
