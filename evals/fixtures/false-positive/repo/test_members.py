"""Tests for member removal."""

import json

from members import remove_member


def test_remove_one_member():
    status, body = remove_member("m1")
    assert status == 200
    assert json.loads(body)["removed"] == "m1"


def test_unknown_member_is_404():
    status, _ = remove_member("ghost")
    assert status == 404
