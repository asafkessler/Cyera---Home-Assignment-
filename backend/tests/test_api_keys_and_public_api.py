import uuid

from tests.fake_jira import SITE_URL, VALID_EMAIL, VALID_TOKEN

KEYS = "/api/keys"
FINDINGS = "/api/v1/findings"
FINDING = {
    "project_key": "SCRUM",
    "summary": "Expiring credential: deploy-key-7",
    "description": "Expires in 3 days.",
    "severity": "medium",
    "identity_type": "api_key",
}


def _new_key(client, name="scanner") -> dict:
    r = client.post(KEYS, json={"name": name})
    assert r.status_code == 201, r.text
    return r.json()


# --- API key management (session-authenticated) -------------------------------------

def test_create_key_shows_full_key_once_and_lists_prefix_only(client, user):
    created = _new_key(client)
    assert created["key"].startswith("ihk_")
    assert created["key_prefix"] == created["key"][:12]
    listed = client.get(KEYS).json()
    assert [k["id"] for k in listed] == [created["id"]]
    assert "key" not in listed[0]
    assert listed[0]["revoked_at"] is None


def test_keys_require_session(client):
    client.post("/api/auth/logout")
    assert client.get(KEYS).status_code == 401
    assert client.post(KEYS, json={"name": "x"}).status_code == 401


def test_revoke_key_is_scoped_to_owner(client, user):
    created = _new_key(client)
    client.post("/api/auth/logout")
    client.post("/api/auth/register", json={"email": f"{uuid.uuid4().hex[:6]}@example.com", "password": "long-enough-pw"})
    assert client.delete(f"{KEYS}/{created['id']}").status_code == 404   # not mine
    assert client.get(KEYS).json() == []                                  # and not visible


# --- Public API (API-key-authenticated) -----------------------------------------------

def test_public_api_rejects_missing_wrong_and_revoked_keys(client, connected_user):
    created = _new_key(client)
    client.cookies.clear()  # the public API must not accept the session cookie

    r = client.post(FINDINGS, json=FINDING)
    assert r.status_code == 401 and r.json()["error"]["code"] == "invalid_api_key"

    r = client.post(FINDINGS, json=FINDING, headers={"X-API-Key": "ihk_not-a-real-key"})
    assert r.status_code == 401

    # revoke and retry with the real key
    client.post("/api/auth/login", json={"email": connected_user["email"], "password": "long-enough-pw"})
    assert client.delete(f"{KEYS}/{created['id']}").status_code == 204
    client.cookies.clear()
    r = client.post(FINDINGS, json=FINDING, headers={"X-API-Key": created["key"]})
    assert r.status_code == 401


def test_public_api_creates_ticket_as_key_owner(client, connected_user, fake_jira):
    created = _new_key(client, name="ci-pipeline")
    client.cookies.clear()

    r = client.post(FINDINGS, json=FINDING, headers={"X-API-Key": created["key"]})
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["issue_key"] == "SCRUM-1"
    assert body["source"] == "api"
    assert "IdentityHub API (automated)" in str(fake_jira.created[0]["fields"]["description"])

    # The ticket shows up in the owner's recent-tickets view, and last_used_at was recorded.
    client.post("/api/auth/login", json={"email": connected_user["email"], "password": "long-enough-pw"})
    recent = client.get("/api/tickets", params={"project_key": "SCRUM"}).json()
    assert [t["issue_key"] for t in recent] == ["SCRUM-1"]
    assert client.get(KEYS).json()[0]["last_used_at"] is not None


def test_public_api_when_owner_has_no_jira(client, user):
    created = _new_key(client)
    client.cookies.clear()
    r = client.post(FINDINGS, json=FINDING, headers={"X-API-Key": created["key"]})
    assert r.status_code == 409
    assert r.json()["error"]["code"] == "jira_not_connected"


def test_public_api_validation_and_project_errors(client, connected_user):
    created = _new_key(client)
    headers = {"X-API-Key": created["key"]}
    client.cookies.clear()

    r = client.post(FINDINGS, json={"project_key": "SCRUM"}, headers=headers)
    assert r.status_code == 422
    assert {f["field"] for f in r.json()["error"]["details"]["fields"]} == {"summary", "description"}

    r = client.post(FINDINGS, json={**FINDING, "project_key": "NOPE"}, headers=headers)
    assert r.status_code == 404 and r.json()["error"]["code"] == "project_not_found"


def test_public_api_lists_projects(client, connected_user):
    created = _new_key(client)
    client.cookies.clear()
    r = client.get("/api/v1/projects", headers={"X-API-Key": created["key"]})
    assert r.status_code == 200
    assert [p["key"] for p in r.json()] == ["SCRUM", "OPS"]


def test_openapi_documents_api_key_scheme_and_error_examples(client):
    spec = client.get("/api/openapi.json").json()
    assert "ApiKey" in spec["components"]["securitySchemes"]
    assert spec["components"]["securitySchemes"]["ApiKey"]["name"] == "X-API-Key"
    post = spec["paths"]["/api/v1/findings"]["post"]
    assert post["security"] == [{"ApiKey": []}]
    examples = post["responses"]["401"]["content"]["application/json"]["examples"]
    assert examples["invalid_api_key"]["value"]["error"]["code"] == "invalid_api_key"
    assert set(post["responses"]) >= {"201", "401", "404", "409", "422", "502"}
