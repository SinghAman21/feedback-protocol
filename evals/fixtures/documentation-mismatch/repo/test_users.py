"""Tests for user routes."""

import json

from users import dispatch


def test_get_user():
    status, body = dispatch("GET", "/api/v1/users/u1")
    assert status == 200
    assert json.loads(body)["id"] == "u1"


def test_delete_user_via_post():
    status, body = dispatch("POST", "/api/v1/users/u1/delete")
    assert status == 200
    assert json.loads(body)["deleted"] == "u1"


def test_unknown_route_is_404():
    status, _ = dispatch("DELETE", "/api/v1/users/u1")
    assert status == 404
