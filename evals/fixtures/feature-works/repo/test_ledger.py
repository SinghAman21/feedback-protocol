"""Tests for the customer ledger export."""

from ledger import CustomerStore, handle_export_request


def _store_with_two():
    store = CustomerStore()
    store.add("c1", "Ada", "ada@example.com")
    store.add("c2", "Bob", "bob@example.com")
    return store


def test_export_json_round_trip():
    import json

    payload = json.loads(_store_with_two().export("json"))
    assert [c["id"] for c in payload["customers"]] == ["c1", "c2"]


def test_export_empty_store():
    import json

    assert json.loads(CustomerStore().export()) == {"customers": []}


def test_export_rejects_unknown_format():
    try:
        CustomerStore().export("xml")
    except ValueError as exc:
        assert "unsupported export format" in str(exc)
    else:
        raise AssertionError("expected ValueError")


def test_handler_defaults_to_json():
    status, body = handle_export_request({})
    assert status == 200
    assert "customers" in body


def test_add_validates_input():
    try:
        CustomerStore().add("", "No", "no@example.com")
    except ValueError:
        pass
    else:
        raise AssertionError("expected ValueError")
