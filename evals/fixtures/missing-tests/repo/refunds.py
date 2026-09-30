"""Refund calculation (billing helpers)."""

from __future__ import annotations


def calculate_refund_cents(paid_cents: int, refunded_cents: int) -> int:
    """Remaining refundable amount. Never negative; zero-amount refunds
    are valid and return 0."""
    if paid_cents < 0 or refunded_cents < 0:
        raise ValueError("amounts must be non-negative")
    if refunded_cents > paid_cents:
        raise ValueError("cannot refund more than was paid")
    return paid_cents - refunded_cents
