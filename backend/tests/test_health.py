def test_health_reports_ok(client):
    response = client.get("/api/health")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["environment"] == "test"


def test_openapi_is_served_under_api_prefix(client):
    assert client.get("/api/openapi.json").status_code == 200
    assert client.get("/api/docs").status_code == 200


def test_unknown_route_is_404_in_uniform_shape(client):
    r = client.get("/api/does-not-exist")
    assert r.status_code == 404
    assert r.json()["error"]["code"] == "not_found"


def test_wrong_method_is_405_in_uniform_shape(client):
    r = client.delete("/api/health")
    assert r.status_code == 405
    assert r.json()["error"]["code"] == "method_not_allowed"
