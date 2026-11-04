#!/usr/bin/env python3
"""
Prepare a throwaway IdentityHub account for a CI run of the digest.

In GitHub Actions the app is started fresh (empty database) inside the job, so
there is no user and no API key yet. This script does what a person would do
in the UI: register, connect the Jira workspace (from secrets), and create an
API key. It prints the key for the workflow to use (masked in the log).

Environment: IDENTITYHUB_API_URL, JIRA_SITE_URL, JIRA_EMAIL, JIRA_API_TOKEN
"""
import os
import secrets
import sys

import httpx


def main() -> int:
    api_url = os.environ.get("IDENTITYHUB_API_URL", "http://localhost:8000").rstrip("/")
    missing = [name for name in ("JIRA_SITE_URL", "JIRA_EMAIL", "JIRA_API_TOKEN") if not os.environ.get(name)]
    if missing:
        print(f"[bootstrap] Missing environment variables: {', '.join(missing)}", file=sys.stderr)
        return 2

    with httpx.Client(base_url=api_url, timeout=30) as http:
        email = f"ci-{secrets.token_hex(4)}@example.com"
        password = secrets.token_urlsafe(16)
        _check(http.post("/api/auth/register", json={"email": email, "password": password}), "register")
        _check(
            http.put("/api/jira/connection", json={
                "site_url": os.environ["JIRA_SITE_URL"],
                "email": os.environ["JIRA_EMAIL"],
                "api_token": os.environ["JIRA_API_TOKEN"],
            }),
            "connect Jira",
        )
        created = _check(http.post("/api/keys", json={"name": "github-actions-blog-digest"}), "create API key").json()

    key = created["key"]
    print(f"::add-mask::{key}")  # never show the key in the Actions log
    github_env = os.environ.get("GITHUB_ENV")
    if github_env:
        with open(github_env, "a", encoding="utf-8") as fh:
            fh.write(f"IDENTITYHUB_API_KEY={key}\n")
    else:
        print(f"IDENTITYHUB_API_KEY={key}")
    print("[bootstrap] Account registered, Jira connected, API key created.")
    return 0


def _check(response: httpx.Response, step: str) -> httpx.Response:
    if response.status_code >= 400:
        print(f"[bootstrap] Failed to {step}: HTTP {response.status_code} {response.text[:300]}", file=sys.stderr)
        sys.exit(2)
    return response


if __name__ == "__main__":
    sys.exit(main())
