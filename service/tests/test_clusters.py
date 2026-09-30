"""Deterministic clustering: grouping, fields, stability, filters."""

from __future__ import annotations

from fastapi.testclient import TestClient

from service.app import create_app
from service.cluster import cluster_id_for
from service.tests.conftest import TEST_KEY, submit

# The v0.5 sample: three reporters, one underlying problem.
SAMPLE = [
    {
        "service": {"name": "users-api", "environment": "production"},
        "type": "missing_feature",
        "summary": "GET /users is too large",
        "goal": "Export the user list",
        "attempt": {"method": "GET", "path": "/api/v1/users"},
        "observed": {"status": 200, "item_count": 100000},
        "missing_capability": "pagination",
        "agent": {"name": "reporter-a"},
    },
    {
        "service": "users-api",
        "type": "missing_feature",
        "summary": "GET /users needs pagination",
        "attempt": {"method": "GET", "path": "/api/v1/users"},
        "observed": {"status": 200, "item_count": 100000},
        "missing_capability": "pagination",
        "agent": {"name": "reporter-b"},
    },
    {
        "service": {"name": "users-api", "environment": "production"},
        "type": "missing_feature",
        "summary": "GET /users returned 100k records",
        "attempt": {"method": "GET", "path": "/api/v1/users"},
        "observed": {"status": 200, "item_count": 100000},
        "missing_capability": "pagination",
        "agent": {"name": "reporter-c"},
    },
]


def seed_sample(client: TestClient, headers: dict[str, str]) -> list[str]:
    return [submit(client, headers, dict(p)) for p in SAMPLE]


def test_sample_reports_form_one_cluster(
    client: TestClient, auth_headers: dict[str, str]
) -> None:
    ids = seed_sample(client, auth_headers)
    body = client.get("/clusters", headers=auth_headers).json()
    assert body["total"] == 1
    cluster = body["items"][0]
    assert cluster["cluster_id"].startswith("cluster_")
    assert cluster["service"] == "users-api"
    assert cluster["type"] == "missing_feature"
    assert cluster["endpoint"] == "/api/v1/users"
    assert cluster["count"] == 3
    assert cluster["first_seen"] <= cluster["last_seen"]
    assert cluster["status_breakdown"] == {"new": 3}
    assert set(cluster["feedback_ids"]) == set(ids)
    # Representative is the earliest report (reporter A).
    assert cluster["representative"]["feedback"]["agent"]["name"] == "reporter-a"
    assert cluster["representative"]["id"] == ids[0]


def test_cluster_id_is_deterministic(
    client: TestClient, auth_headers: dict[str, str], tmp_path
) -> None:
    seed_sample(client, auth_headers)
    first = client.get("/clusters", headers=auth_headers).json()["items"][0]["cluster_id"]
    # Same ID on repeat reads…
    second = client.get("/clusters", headers=auth_headers).json()["items"][0]["cluster_id"]
    assert first == second
    # …matches the pure function…
    assert first == cluster_id_for(
        ("users-api", "missing_feature", "GET", "/api/v1/users", "pagination")
    )
    # …and survives a reopen of the same database file.
    db_path = tmp_path / "reopen.db"
    app1 = create_app(db_path=str(db_path), api_key=TEST_KEY)
    from fastapi.testclient import TestClient as TC

    with TC(app1) as c1:
        for p in SAMPLE:
            assert c1.post("/feedback", json=dict(p), headers=auth_headers).status_code == 201
        cid1 = c1.get("/clusters", headers=auth_headers).json()["items"][0]["cluster_id"]
    app2 = create_app(db_path=str(db_path), api_key=TEST_KEY)
    with TC(app2) as c2:
        cid2 = c2.get("/clusters", headers=auth_headers).json()["items"][0]["cluster_id"]
    assert cid1 == cid2 == first


def test_different_type_splits_clusters(
    client: TestClient, auth_headers: dict[str, str]
) -> None:
    seed_sample(client, auth_headers)
    submit(
        client,
        auth_headers,
        {
            "service": "users-api",
            "type": "bug",
            "summary": "500 on users",
            "attempt": {"method": "GET", "path": "/api/v1/users"},
        },
    )
    assert client.get("/clusters", headers=auth_headers).json()["total"] == 2


def test_different_service_and_capability_split_clusters(
    client: TestClient, auth_headers: dict[str, str]
) -> None:
    seed_sample(client, auth_headers)
    submit(
        client,
        auth_headers,
        {
            "service": "payments-api",
            "type": "missing_feature",
            "summary": "needs pagination",
            "attempt": {"method": "GET", "path": "/api/v1/users"},
            "missing_capability": "pagination",
        },
    )
    submit(
        client,
        auth_headers,
        {
            "service": "users-api",
            "type": "missing_feature",
            "summary": "needs filtering",
            "attempt": {"method": "GET", "path": "/api/v1/users"},
            "missing_capability": "filtering",
        },
    )
    assert client.get("/clusters", headers=auth_headers).json()["total"] == 3


def test_cluster_detail_and_filters(
    client: TestClient, auth_headers: dict[str, str]
) -> None:
    seed_sample(client, auth_headers)
    cid = client.get("/clusters", headers=auth_headers).json()["items"][0]["cluster_id"]
    detail = client.get(f"/clusters/{cid}", headers=auth_headers)
    assert detail.status_code == 200
    assert detail.json()["count"] == 3
    assert client.get("/clusters/nope", headers=auth_headers).status_code == 404
    # Filters narrow the grouping input.
    assert client.get("/clusters?service=users-api", headers=auth_headers).json()["total"] == 1
    assert client.get("/clusters?service=other", headers=auth_headers).json()["total"] == 0
    assert client.get("/clusters?type=bug", headers=auth_headers).json()["total"] == 0
    assert client.get("/clusters?type=nope", headers=auth_headers).status_code == 400


def test_empty_store_has_no_clusters(client: TestClient, auth_headers: dict[str, str]) -> None:
    assert client.get("/clusters", headers=auth_headers).json() == {"items": [], "total": 0}
