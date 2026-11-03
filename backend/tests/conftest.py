"""
Test configuration.

Settings are read at import time, so the environment is prepared before the
app is imported: an isolated temporary SQLite file and throwaway secrets.
"""
import os
import tempfile
from pathlib import Path

import pytest
from cryptography.fernet import Fernet

_TMP = Path(tempfile.mkdtemp(prefix="identityhub-tests-"))
os.environ["DATABASE_URL"] = f"sqlite:///{_TMP / 'test.db'}"
os.environ["APP_SECRET_KEY"] = "test-secret-key-that-is-definitely-long-enough"
os.environ["APP_ENCRYPTION_KEY"] = Fernet.generate_key().decode()
os.environ["APP_ENV"] = "test"

from fastapi.testclient import TestClient  # noqa: E402

from app.main import app  # noqa: E402


@pytest.fixture
def client() -> TestClient:
    with TestClient(app) as c:  # runs the lifespan (creates tables)
        yield c


# --- Fake Jira -------------------------------------------------------------------

import functools  # noqa: E402

from app.jira import client as jira_client_module  # noqa: E402
from app.jira import service as jira_service_module  # noqa: E402
from tests.fake_jira import SITE_URL, VALID_EMAIL, VALID_TOKEN, FakeJira  # noqa: E402


@pytest.fixture
def fake_jira(monkeypatch) -> FakeJira:
    """Route every JiraClient the app builds to an in-process fake Jira."""
    fake = FakeJira()
    patched = functools.partial(jira_client_module.JiraClient, transport=fake.transport())
    monkeypatch.setattr(jira_service_module, "JiraClient", patched)
    return fake


@pytest.fixture
def user(client) -> dict:
    """A fresh, logged-in user (the client keeps the session cookie)."""
    import uuid
    email = f"user-{uuid.uuid4().hex[:8]}@example.com"
    r = client.post("/api/auth/register", json={"email": email, "password": "long-enough-pw"})
    assert r.status_code == 201
    return r.json()


@pytest.fixture
def connected_user(client, user, fake_jira) -> dict:
    """A logged-in user whose Jira workspace is connected to the fake."""
    r = client.put("/api/jira/connection", json={"site_url": SITE_URL, "email": VALID_EMAIL, "api_token": VALID_TOKEN})
    assert r.status_code == 200, r.text
    return user
