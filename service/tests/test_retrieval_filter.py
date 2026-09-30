"""Retrieval, listing, pagination, and filtering."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from service.tests.conftest import submit


@pytest.fixture()
def seeded(client: TestClient, auth_headers: dict[str, str]) -> list[str]:
    payloads = [
        {"service": "users-api", "type": "bug", "summary": "bug one"},
        {"service": "users-api", "type": "missing_feature", "summary": "feature one"},
        {"service": "payments-api", "type": "bug", "summary": "bug two"},
    ]
    return [submit(client, auth_headers, p) for p in payloads]


def test_get_unknown_id_is_404(client: TestClient, auth_headers: dict[str, str]) -> None:
    assert client.get("/feedback/fb_doesnotexist0000000000", headers=auth_headers).status_code == 404


def test_list_pagination(
    client: TestClient, auth_headers: dict[str, str], seeded: list[str]
) -> None:
    page1 = client.get("/feedback?limit=2&offset=0", headers=auth_headers).json()
    assert page1["total"] == 3
    assert [i["id"] for i in page1["items"]] == seeded[:2]
    page2 = client.get("/feedback?limit=2&offset=2", headers=auth_headers).json()
    assert [i["id"] for i in page2["items"]] == seeded[2:]


def test_filter_by_service(
    client: TestClient, auth_headers: dict[str, str], seeded: list[str]
) -> None:
    body = client.get("/feedback?service=users-api", headers=auth_headers).json()
    assert body["total"] == 2
    assert {i["id"] for i in body["items"]} == set(seeded[:2])


def test_filter_by_type(
    client: TestClient, auth_headers: dict[str, str], seeded: list[str]
) -> None:
    body = client.get("/feedback?type=bug", headers=auth_headers).json()
    assert body["total"] == 2
    assert {i["id"] for i in body["items"]} == {seeded[0], seeded[2]}


def test_filter_by_status(
    client: TestClient, auth_headers: dict[str, str], seeded: list[str]
) -> None:
    client.patch(f"/feedback/{seeded[0]}", json={"status": "investigating"}, headers=auth_headers)
    body = client.get("/feedback?status=investigating", headers=auth_headers).json()
    assert body["total"] == 1
    assert body["items"][0]["id"] == seeded[0]
    assert client.get("/feedback?status=new", headers=auth_headers).json()["total"] == 2


def test_combined_filters(
    client: TestClient, auth_headers: dict[str, str], seeded: list[str]
) -> None:
    body = client.get(
        "/feedback?service=users-api&type=missing_feature&status=new",
        headers=auth_headers,
    ).json()
    assert body["total"] == 1
    assert body["items"][0]["id"] == seeded[1]


def test_invalid_filters_are_400(client: TestClient, auth_headers: dict[str, str]) -> None:
    assert client.get("/feedback?type=nope", headers=auth_headers).status_code == 400
    assert client.get("/feedback?status=nope", headers=auth_headers).status_code == 400
    assert client.get("/feedback?limit=0", headers=auth_headers).status_code == 400
    assert client.get("/feedback?limit=5000", headers=auth_headers).status_code == 400
    assert client.get("/feedback?offset=-1", headers=auth_headers).status_code == 400


def test_service_scoped_listing(
    client: TestClient, auth_headers: dict[str, str], seeded: list[str]
) -> None:
    body = client.get("/services/users-api/feedback", headers=auth_headers).json()
    assert body["total"] == 2
    body = client.get("/services/users-api/feedback?type=bug", headers=auth_headers).json()
    assert body["total"] == 1
    assert client.get("/services/nonexistent/feedback", headers=auth_headers).json() == {
        "items": [],
        "total": 0,
    }
