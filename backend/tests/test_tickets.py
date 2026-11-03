import json

TICKETS = "/api/tickets"
VALID = {
    "project_key": "scrum",
    "summary": "Stale service account: svc-deploy-prod",
    "description": "No auth events in 94 days.\nOwner: platform team.",
    "severity": "high",
    "identity_type": "service_account",
}


def test_create_ticket_creates_issue_and_records_it(client, connected_user, fake_jira):
    r = client.post(TICKETS, json=VALID)
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["issue_key"] == "SCRUM-1"
    assert body["issue_url"] == "https://fake.atlassian.net/browse/SCRUM-1"
    assert body["project_key"] == "SCRUM"          # normalised to upper case
    assert body["source"] == "ui"

    sent = fake_jira.created[0]["fields"]
    assert sent["project"] == {"key": "SCRUM"}
    assert sent["issuetype"] == {"name": "Task"}   # default
    assert sent["summary"] == VALID["summary"]
    assert "identityhub" in sent["labels"]

    adf = sent["description"]
    assert adf["type"] == "doc" and adf["version"] == 1
    flat = json.dumps(adf)
    assert "Severity" in flat and "High" in flat
    assert "Service account" in flat
    assert "IdentityHub web app" in flat
    assert "No auth events in 94 days." in flat and "Owner: platform team." in flat


def test_create_ticket_with_explicit_issue_type(client, connected_user, fake_jira):
    r = client.post(TICKETS, json={**VALID, "issue_type": "Bug"})
    assert r.status_code == 201
    assert fake_jira.created[0]["fields"]["issuetype"] == {"name": "Bug"}


def test_create_ticket_requires_connection(client, user):
    r = client.post(TICKETS, json=VALID)
    assert r.status_code == 409
    assert r.json()["error"]["code"] == "jira_not_connected"


def test_create_ticket_unknown_project(client, connected_user):
    r = client.post(TICKETS, json={**VALID, "project_key": "NOPE"})
    assert r.status_code == 404
    assert r.json()["error"]["code"] == "project_not_found"


def test_create_ticket_unknown_issue_type_is_actionable(client, connected_user):
    r = client.post(TICKETS, json={**VALID, "issue_type": "Incident"})
    assert r.status_code == 422
    err = r.json()["error"]
    assert 'Issue type "Incident" is not available in project SCRUM' in err["message"]
    assert err["details"]["fields"][0]["field"] == "issue_type"


def test_create_ticket_validates_fields(client, connected_user):
    r = client.post(TICKETS, json={"project_key": "SCRUM", "summary": "  ", "description": "x", "severity": "urgent"})
    assert r.status_code == 422
    fields = {f["field"] for f in r.json()["error"]["details"]["fields"]}
    assert {"summary", "severity"} <= fields


def test_recent_tickets_are_scoped_ordered_and_limited(client, connected_user, fake_jira):
    for i in range(12):
        assert client.post(TICKETS, json={**VALID, "summary": f"finding {i}"}).status_code == 201
    # one ticket in another project must not appear under SCRUM
    assert client.post(TICKETS, json={**VALID, "project_key": "OPS", "summary": "ops finding"}).status_code == 201

    r = client.get(TICKETS, params={"project_key": "scrum"})
    assert r.status_code == 200
    items = r.json()
    assert len(items) == 10                                   # default limit
    assert items[0]["summary"] == "finding 11"                # newest first
    assert all(t["project_key"] == "SCRUM" for t in items)

    assert len(client.get(TICKETS, params={"project_key": "SCRUM", "limit": 3}).json()) == 3
    assert [t["summary"] for t in client.get(TICKETS, params={"project_key": "OPS"}).json()] == ["ops finding"]


def test_recent_tickets_requires_project_key(client, connected_user):
    assert client.get(TICKETS).status_code == 422


def test_recent_tickets_are_per_user(client, connected_user, fake_jira):
    assert client.post(TICKETS, json=VALID).status_code == 201
    client.post("/api/auth/logout")
    client.post("/api/auth/register", json={"email": "other@example.com", "password": "long-enough-pw"})
    assert client.get(TICKETS, params={"project_key": "SCRUM"}).json() == []
