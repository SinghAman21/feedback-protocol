"""Centralized feedback service (v0.5).

Receives protocol-compliant feedback, stores it in SQLite, groups it
into deterministic clusters, and exposes triage status — so individual
reports become actionable engineering signals.

Pipeline: feedback → centralized storage → aggregation → human triage.
"""
