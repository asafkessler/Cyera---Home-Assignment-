"""The uniform error body is a contract for the UI and external callers."""
from fastapi import APIRouter
from fastapi.testclient import TestClient
from pydantic import BaseModel

from app.core.errors import JiraNotConnected
from app.main import app

_probe = APIRouter(prefix="/api/_test")


class _Payload(BaseModel):
    summary: str


@_probe.post("/validate")
def _validate(payload: _Payload):
    return payload


@_probe.get("/app-error")
def _app_error():
    raise JiraNotConnected()


@_probe.get("/boom")
def _boom():
    raise RuntimeError("secret internal detail")


app.include_router(_probe)


def test_app_error_has_uniform_shape():
    with TestClient(app) as client:
        r = client.get("/api/_test/app-error")
    assert r.status_code == 409
    assert r.json() == {
        "error": {
            "code": "jira_not_connected",
            "message": JiraNotConnected.message,
            "details": {},
        }
    }


def test_validation_error_names_the_field():
    with TestClient(app) as client:
        r = client.post("/api/_test/validate", json={})
    assert r.status_code == 422
    body = r.json()["error"]
    assert body["code"] == "validation_failed"
    assert body["details"]["fields"][0]["field"] == "summary"


def test_unexpected_error_does_not_leak_details():
    with TestClient(app, raise_server_exceptions=False) as client:
        r = client.get("/api/_test/boom")
    assert r.status_code == 500
    assert "secret internal detail" not in r.text
    assert r.json()["error"]["code"] == "internal_error"
