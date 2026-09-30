"""Tests for subscriber export."""

import json

from subscribers import SubscriberList, handle_export_request


def test_export_json_lists_everyone():
    lst = SubscriberList()
    lst.subscribe("a@example.com", "A")
    lst.subscribe("b@example.com")
    assert [s["email"] for s in json.loads(lst.export())["subscribers"]] == [
        "a@example.com",
        "b@example.com",
    ]


def test_export_rejects_csv():
    try:
        SubscriberList().export("csv")
    except ValueError as exc:
        assert "unsupported export format" in str(exc)
    else:
        raise AssertionError("expected ValueError")


def test_handler_returns_400_for_csv():
    status, body = handle_export_request({"format": "csv"})
    assert status == 400
    assert "unsupported export format" in body


def test_subscribe_validates_email():
    try:
        SubscriberList().subscribe("not-an-email")
    except ValueError:
        pass
    else:
        raise AssertionError("expected ValueError")
