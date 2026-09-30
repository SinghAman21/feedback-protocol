"""Tests for account creation."""

import json

from accounts import create_account


def test_create_with_email():
    status, body = create_account({"email": "sam@example.com", "name": "Sam"})
    assert status == 201
    assert json.loads(body)["email"] == "sam@example.com"


def test_missing_email_is_400():
    status, body = create_account({"name": "Sam"})
    assert status == 400
    assert "email" in json.loads(body)["error"]


def test_misspelled_field_is_400():
    status, body = create_account({"e-mail": "sam@example.com"})
    assert status == 400
