"""Tests for invoice rendering."""

from billing import render_invoice


def test_renders_invoice_with_due_date():
    import json

    status, body = render_invoice("inv_1")
    assert status == 200
    assert json.loads(body)["due_label"] == "due 2026-04-01"


def test_unknown_invoice_is_404():
    import json

    status, body = render_invoice("nope")
    assert status == 404
    assert json.loads(body)["error"] == "not_found"
