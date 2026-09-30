"""Tests for event listing."""

import json

from events import handle_list_events


def test_list_returns_200_with_events_key():
    status, body = handle_list_events({"limit": 2})
    assert status == 200
    payload = json.loads(body)
    assert [e["id"] for e in payload["events"]] == ["evt_0", "evt_1"]


def test_pagination_second_page():
    status, body = handle_list_events({"limit": 2, "page": 2})
    assert status == 200
    assert [e["id"] for e in json.loads(body)["events"]] == ["evt_2", "evt_3"]


def test_limit_defaults_to_50():
    status, body = handle_list_events({})
    assert status == 200
    assert len(json.loads(body)["events"]) == 50
