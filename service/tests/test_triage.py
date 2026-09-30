"""Triage: reports start new, humans move them, nothing auto-confirms."""

from __future__ import annotations

from fastapi.testclient import TestClient

from service.models import TRIAGE_STATUSES
from service.tests.conftest import submit
from service.tests.test_clusters import seed_sample


def test_new_is_default_and_all_statuses_reachable(
    client: TestClient, auth_headers: dict[str, str]
) -> None:
    fid = submit(client, auth_headers, {"type": "bug", "summary": "x"})
    assert client.get(f"/feedback/{fid}", headers=auth_headers).json()["status"] == "new"
    for status in TRIAGE_STATUSES:
        resp = client.patch(f"/feedback/{fid}", json={"status": status}, headers=auth_headers)
        assert resp.status_code == 200, status
        assert resp.json()["status"] == status


def test_invalid_triage_updates_are_400(
    client: TestClient, auth_headers: dict[str, str]
) -> None:
    fid = submit(client, auth_headers, {"type": "bug", "summary": "x"})
    assert client.patch(f"/feedback/{fid}", json={"status": "bug"}, headers=auth_headers).status_code == 400
    assert client.patch(f"/feedback/{fid}", json={}, headers=auth_headers).status_code == 400
    resp = client.patch(
        f"/feedback/{fid}", content=b"{bad",
        headers={**auth_headers, "Content-Type": "application/json"},
    )
    assert resp.status_code == 400
    # Status unchanged after rejected updates.
    assert client.get(f"/feedback/{fid}", headers=auth_headers).json()["status"] == "new"


def test_unknown_feedback_is_404(client: TestClient, auth_headers: dict[str, str]) -> None:
    resp = client.patch(
        "/feedback/fb_doesnotexist0000000000", json={"status": "accepted"}, headers=auth_headers
    )
    assert resp.status_code == 404


def test_cluster_bulk_triage(
    client: TestClient, auth_headers: dict[str, str]
) -> None:
    ids = seed_sample(client, auth_headers)
    cid = client.get("/clusters", headers=auth_headers).json()["items"][0]["cluster_id"]
    resp = client.patch(f"/clusters/{cid}", json={"status": "investigating"}, headers=auth_headers)
    assert resp.status_code == 200
    assert resp.json() == {"cluster_id": cid, "status": "investigating", "updated": 3}
    for fid in ids:
        assert client.get(f"/feedback/{fid}", headers=auth_headers).json()["status"] == "investigating"
    cluster = client.get(f"/clusters/{cid}", headers=auth_headers).json()
    assert cluster["status_breakdown"] == {"investigating": 3}


def test_cluster_triage_unknown_and_invalid(
    client: TestClient, auth_headers: dict[str, str]
) -> None:
    seed_sample(client, auth_headers)
    assert client.patch("/clusters/nope", json={"status": "accepted"}, headers=auth_headers).status_code == 404
    cid = client.get("/clusters", headers=auth_headers).json()["items"][0]["cluster_id"]
    assert client.patch(f"/clusters/{cid}", json={"status": "nope"}, headers=auth_headers).status_code == 400
