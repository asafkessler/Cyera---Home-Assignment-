import httpx
from sqlalchemy import select

from app.db import SessionLocal
from app.models import JiraConnection
from tests.fake_jira import SITE_URL, VALID_EMAIL, VALID_TOKEN

CONNECTION = "/api/jira/connection"


def test_status_when_not_connected(client, user):
    r = client.get(CONNECTION)
    assert r.status_code == 200
    assert r.json() == {"connected": False, "site_url": None, "email": None,
                        "display_name": None, "connected_at": None, "last_verified_at": None}


def test_connect_verifies_then_stores_encrypted_token(client, user, fake_jira):
    r = client.put(CONNECTION, json={"site_url": SITE_URL, "email": VALID_EMAIL, "api_token": VALID_TOKEN})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["connected"] is True
    assert body["display_name"] == "Asaf Kessler"
    assert "api_token" not in r.text and VALID_TOKEN not in r.text

    # Jira was asked who the token belongs to, before anything was saved.
    assert fake_jira.requests[0].url.path.endswith("/myself")

    with SessionLocal() as db:
        stored = db.scalar(select(JiraConnection).where(JiraConnection.user_id == user["id"]))
    assert stored is not None
    assert stored.api_token_encrypted != VALID_TOKEN
    assert VALID_TOKEN not in stored.api_token_encrypted

    assert client.get("/api/auth/me").json()["jira_connected"] is True


def test_connect_accepts_bare_hostname_and_normalises(client, user, fake_jira):
    r = client.put(CONNECTION, json={"site_url": "fake.atlassian.net/", "email": VALID_EMAIL, "api_token": VALID_TOKEN})
    assert r.status_code == 200
    assert r.json()["site_url"] == "https://fake.atlassian.net"


def test_connect_with_wrong_token_is_rejected_and_nothing_is_stored(client, user, fake_jira):
    r = client.put(CONNECTION, json={"site_url": SITE_URL, "email": VALID_EMAIL, "api_token": "wrong"})
    assert r.status_code == 400
    assert r.json()["error"]["code"] == "jira_auth_failed"
    assert client.get(CONNECTION).json()["connected"] is False


def test_connect_when_jira_unreachable(client, user, fake_jira):
    fake_jira.fail_with = httpx.ConnectError("boom")
    r = client.put(CONNECTION, json={"site_url": SITE_URL, "email": VALID_EMAIL, "api_token": VALID_TOKEN})
    assert r.status_code == 502
    assert r.json()["error"]["code"] == "jira_unavailable"


def test_connect_when_jira_times_out(client, user, fake_jira):
    fake_jira.fail_with = httpx.ReadTimeout("slow")
    r = client.put(CONNECTION, json={"site_url": SITE_URL, "email": VALID_EMAIL, "api_token": VALID_TOKEN})
    assert r.status_code == 502
    assert "did not respond in time" in r.json()["error"]["message"]


def test_connect_rejects_http_and_garbage_urls(client, user):
    for bad in ["http://fake.atlassian.net", "not a url", "https://"]:
        r = client.put(CONNECTION, json={"site_url": bad, "email": VALID_EMAIL, "api_token": VALID_TOKEN})
        assert r.status_code == 422, bad


def test_projects_require_connection(client, user):
    r = client.get("/api/jira/projects")
    assert r.status_code == 409
    assert r.json()["error"]["code"] == "jira_not_connected"


def test_projects_follow_pagination(client, connected_user, fake_jira):
    r = client.get("/api/jira/projects")
    assert r.status_code == 200
    assert [p["key"] for p in r.json()] == ["SCRUM", "OPS"]
    # page_size is 1 in the fake, so two projects took two pages
    searches = [q for q in fake_jira.requests if q.url.path.endswith("/project/search")]
    assert len(searches) == 2


def test_issue_types_exclude_subtasks_and_upper_case_key(client, connected_user):
    r = client.get("/api/jira/projects/scrum/issue-types")
    assert r.status_code == 200
    assert [t["name"] for t in r.json()] == ["Task", "Bug"]


def test_issue_types_for_unknown_project(client, connected_user):
    r = client.get("/api/jira/projects/NOPE/issue-types")
    assert r.status_code == 404
    assert "project NOPE" in r.json()["error"]["message"]


def test_disconnect_removes_credentials(client, connected_user):
    assert client.delete(CONNECTION).status_code == 204
    assert client.get(CONNECTION).json()["connected"] is False
    assert client.get("/api/jira/projects").status_code == 409


def test_connection_is_per_user(client, connected_user, fake_jira):
    # A second user logs in and must not see the first user's connection.
    client.post("/api/auth/logout")
    client.post("/api/auth/register", json={"email": "second@example.com", "password": "long-enough-pw"})
    assert client.get(CONNECTION).json()["connected"] is False
    assert client.get("/api/jira/projects").status_code == 409
