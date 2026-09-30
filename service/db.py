"""SQLite persistence for the centralized feedback service.

``SqliteFeedbackStore`` is the database abstraction: the rest of the
service only depends on its methods (``save`` / ``get`` / ``list`` /
``set_status`` / ``all_for_clustering``), so a PostgreSQL or other
backend can replace it without touching the HTTP layer.

No managed cloud database is required: SQLite (stdlib ``sqlite3``) is
all local development needs.
"""

from __future__ import annotations

import json
import sqlite3
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from feedback_protocol.ids import generate_feedback_id
from feedback_protocol.models import Feedback

SCHEMA = """
CREATE TABLE IF NOT EXISTS feedback (
    id TEXT PRIMARY KEY,
    service_name TEXT NOT NULL,
    service_env TEXT,
    type TEXT NOT NULL,
    status TEXT NOT NULL,
    summary TEXT NOT NULL,
    normalized_summary TEXT NOT NULL,
    method TEXT,
    path TEXT,
    missing_capability TEXT,
    received_at TEXT NOT NULL,
    client_ts TEXT,
    body_json TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_feedback_service ON feedback(service_name);
CREATE INDEX IF NOT EXISTS idx_feedback_type ON feedback(type);
CREATE INDEX IF NOT EXISTS idx_feedback_status ON feedback(status);
CREATE INDEX IF NOT EXISTS idx_feedback_received ON feedback(received_at);
"""

# Columns added after v0.5.0: existing databases are migrated on open.
MIGRATION_COLUMNS = (
    ("service_version", "TEXT"),
    ("session_id", "TEXT"),
    ("trace_id", "TEXT"),
)


def utcnow_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class SqliteFeedbackStore:
    """Thread-safe SQLite store for feedback records."""

    def __init__(self, path: str | Path = "feedback-service.db") -> None:
        self._lock = threading.Lock()
        self._conn = sqlite3.connect(str(path), check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        with self._lock, self._conn:
            self._conn.executescript(SCHEMA)
            existing = {
                row[1]
                for row in self._conn.execute("PRAGMA table_info(feedback)").fetchall()
            }
            for column, ddl in MIGRATION_COLUMNS:
                if column not in existing:
                    self._conn.execute(f"ALTER TABLE feedback ADD COLUMN {column} {ddl}")

    def close(self) -> None:
        with self._lock:
            self._conn.close()

    def save(
        self,
        *,
        feedback: Feedback,
        service_name: str,
        service_env: str | None,
        service_version: str | None = None,
        session_id: str | None = None,
        trace_id: str | None = None,
        normalized_summary: str,
        body_json: str,
    ) -> dict[str, Any]:
        """Persist one scrubbed report; returns the stored row as a dict."""
        received_at = utcnow_iso()
        row = {
            "id": generate_feedback_id(),
            "service_name": service_name,
            "service_env": service_env,
            "service_version": service_version,
            "session_id": session_id,
            "trace_id": trace_id,
            "type": feedback.type,
            "status": "new",
            "summary": feedback.summary,
            "normalized_summary": normalized_summary,
            "method": feedback.attempt.method if feedback.attempt else None,
            "path": feedback.attempt.path if feedback.attempt else None,
            "missing_capability": feedback.missing_capability,
            "received_at": received_at,
            "client_ts": feedback.timestamp.isoformat() if feedback.timestamp else None,
            "body_json": body_json,
        }
        # Regenerate on the (astronomically unlikely) ID collision.
        with self._lock, self._conn:
            while self._conn.execute(
                "SELECT 1 FROM feedback WHERE id = ?", (row["id"],)
            ).fetchone():
                row["id"] = generate_feedback_id()
            self._conn.execute(
                """INSERT INTO feedback
                   (id, service_name, service_env, service_version, session_id,
                    trace_id, type, status, summary,
                    normalized_summary, method, path, missing_capability,
                    received_at, client_ts, body_json)
                   VALUES (:id, :service_name, :service_env, :service_version,
                           :session_id, :trace_id, :type, :status,
                           :summary, :normalized_summary, :method, :path,
                           :missing_capability, :received_at, :client_ts,
                           :body_json)""",
                row,
            )
        return row

    def get(self, feedback_id: str) -> dict[str, Any] | None:
        with self._lock:
            cur = self._conn.execute("SELECT * FROM feedback WHERE id = ?", (feedback_id,))
            row = cur.fetchone()
            return dict(row) if row else None

    def list(
        self,
        *,
        service: str | None = None,
        type: str | None = None,
        status: str | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> tuple[list[dict[str, Any]], int]:
        clauses: list[str] = []
        params: list[Any] = []
        if service is not None:
            clauses.append("service_name = ?")
            params.append(service)
        if type is not None:
            clauses.append("type = ?")
            params.append(type)
        if status is not None:
            clauses.append("status = ?")
            params.append(status)
        where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        with self._lock:
            total = self._conn.execute(
                f"SELECT COUNT(*) FROM feedback {where}", params
            ).fetchone()[0]
            cur = self._conn.execute(
                f"SELECT * FROM feedback {where} "
                f"ORDER BY received_at ASC, id ASC LIMIT ? OFFSET ?",
                [*params, limit, offset],
            )
            return [dict(r) for r in cur.fetchall()], total

    def set_status(self, feedback_id: str, status: str) -> dict[str, Any] | None:
        with self._lock, self._conn:
            cur = self._conn.execute(
                "UPDATE feedback SET status = ? WHERE id = ?", (status, feedback_id)
            )
            if cur.rowcount == 0:
                return None
            row = self._conn.execute(
                "SELECT * FROM feedback WHERE id = ?", (feedback_id,)
            ).fetchone()
            return dict(row) if row else None

    def set_status_for_ids(self, ids: list[str], status: str) -> int:
        if not ids:
            return 0
        with self._lock, self._conn:
            cur = self._conn.execute(
                f"UPDATE feedback SET status = ? WHERE id IN "
                f"({','.join('?' for _ in ids)})",
                [status, *ids],
            )
            return cur.rowcount

    def all_for_clustering(
        self, *, service: str | None = None, type: str | None = None
    ) -> list[dict[str, Any]]:
        clauses, params = [], []
        if service is not None:
            clauses.append("service_name = ?")
            params.append(service)
        if type is not None:
            clauses.append("type = ?")
            params.append(type)
        where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        with self._lock:
            cur = self._conn.execute(
                f"SELECT * FROM feedback {where} ORDER BY received_at ASC, id ASC",
                params,
            )
            return [dict(r) for r in cur.fetchall()]
