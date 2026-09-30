"""Security: auth on everything except health/discovery, no secret leakage."""

from __future__ import annotations

from fastapi.testclient import TestClient

PROTECTED = [
    ("POST", "/feedback", {"type": "bug", "summary": "x"}),
    ("GET", "/feedback", None),
    ("GET", "/feedback/fb_123", None),
    ("GET", "/services/users-api/feedback", None),
    ("GET", "/clusters", None),
    ("GET", "/clusters/cluster_123", None),
    ("PATCH", "/feedback/fb_123", {"status": "accepted"}),
    ("PATCH", "/clusters/cluster_123", {"status": "accepted"}),
]


def test_public_endpoints_need_no_key(client: TestClient) -> None:
    assert client.get("/health").status_code == 200
    discovery = client.get("/.well-known/feedback-protocol")
    assert discovery.status_code == 200
    assert discovery.json() == {
        "version": "0.1",
        "feedback_endpoint": "/feedback",
        "methods": ["POST"],
    }


def test_protected_endpoints_reject_anonymous(client: TestClient) -> None:
    for method, path, body in PROTECTED:
        resp = client.request(method, path, json=body)
        assert resp.status_code == 401, (method, path)


def test_wrong_key_and_scheme_rejected(client: TestClient) -> None:
    assert client.get("/feedback", headers={"Authorization": "Bearer wrong"}).status_code == 401
    assert client.get("/feedback", headers={"Authorization": "Token x"}).status_code == 401
    assert client.get("/feedback", headers={"Authorization": "Bearer "}).status_code == 401
    assert client.get("/feedback", headers={"Authorization": ""}).status_code == 401


def test_no_secret_values_in_any_response(
    client: TestClient, auth_headers: dict[str, str]
) -> None:
    payload = {
        "service": "users-api",
        "type": "bug",
        "summary": "login fails",
        "metadata": {"password": "hunter2", "token": "tok-abc", "note": "plain"},
    }
    fid = client.post("/feedback", json=payload, headers=auth_headers).json()["id"]
    bodies = [
        client.get(f"/feedback/{fid}", headers=auth_headers).text,
        client.get("/feedback", headers=auth_headers).text,
        client.get("/clusters", headers=auth_headers).text,
    ]
    for text in bodies:
        assert "hunter2" not in text
        assert "tok-abc" not in text
        assert "plain" in text
