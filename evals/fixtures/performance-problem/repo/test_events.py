"""Tests for event listing."""

import json

from events import _all_events, handle_list_events


def test_list_returns_200_with_events_key():
    status, body = handle_list_events({})
    assert status == 200
    payload = json.loads(body)
    assert "events" in payload
    assert len(payload["events"]) == 100_000


def test_events_have_ids():
    assert _all_events()[0]["id"] == "evt_0"
