"""Tests for refund calculation (stdlib only)."""

from refunds import calculate_refund_cents


def test_partial_refund():
    assert calculate_refund_cents(1000, 400) == 600


def test_full_refund():
    assert calculate_refund_cents(1000, 1000) == 0


def test_over_refund_rejected():
    try:
        calculate_refund_cents(1000, 1200)
    except ValueError:
        pass
    else:
        raise AssertionError("expected ValueError")


def test_negative_amounts_rejected():
    try:
        calculate_refund_cents(-5, 0)
    except ValueError:
        pass
    else:
        raise AssertionError("expected ValueError")
