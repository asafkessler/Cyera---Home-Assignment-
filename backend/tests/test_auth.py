import uuid

REGISTER = "/api/auth/register"
LOGIN = "/api/auth/login"
LOGOUT = "/api/auth/logout"
ME = "/api/auth/me"


def _email() -> str:
    return f"user-{uuid.uuid4().hex[:8]}@example.com"


def test_register_logs_in_and_sets_httponly_cookie(client):
    r = client.post(REGISTER, json={"email": _email(), "password": "long-enough-pw"})
    assert r.status_code == 201
    assert r.json()["jira_connected"] is False
    cookie = r.headers["set-cookie"]
    assert "identityhub_session=" in cookie
    assert "HttpOnly" in cookie and "SameSite=lax" in cookie.replace("Lax", "lax")
    assert client.get(ME).status_code == 200


def test_register_normalises_email_and_rejects_duplicates(client):
    email = _email()
    assert client.post(REGISTER, json={"email": email.upper(), "password": "long-enough-pw"}).status_code == 201
    r = client.post(REGISTER, json={"email": f"  {email} ", "password": "long-enough-pw"})
    assert r.status_code == 409
    assert r.json()["error"]["code"] == "email_already_registered"


def test_register_validates_input(client):
    r = client.post(REGISTER, json={"email": "not-an-email", "password": "short"})
    assert r.status_code == 422
    fields = {f["field"] for f in r.json()["error"]["details"]["fields"]}
    assert fields == {"email", "password"}


def test_login_wrong_password_and_unknown_email_look_identical(client):
    email = _email()
    client.post(REGISTER, json={"email": email, "password": "long-enough-pw"})
    client.post(LOGOUT)
    wrong = client.post(LOGIN, json={"email": email, "password": "nope-nope-nope"})
    unknown = client.post(LOGIN, json={"email": _email(), "password": "nope-nope-nope"})
    assert wrong.status_code == unknown.status_code == 401
    assert wrong.json() == unknown.json()


def test_me_requires_session(client):
    client.post(LOGOUT)
    r = client.get(ME)
    assert r.status_code == 401
    assert r.json()["error"]["code"] == "not_authenticated"


def test_logout_revokes_session_server_side(client):
    client.post(REGISTER, json={"email": _email(), "password": "long-enough-pw"})
    token = client.cookies.get("identityhub_session")
    assert client.post(LOGOUT).status_code == 204
    # Even if a client kept the old cookie, the server no longer honours it.
    client.cookies.set("identityhub_session", token)
    assert client.get(ME).status_code == 401


def test_forged_cookie_is_rejected(client):
    client.cookies.set("identityhub_session", "definitely-not-a-real-token")
    assert client.get(ME).status_code == 401
