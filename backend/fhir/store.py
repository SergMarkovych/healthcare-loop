"""
SQLite snapshot store.

Why snapshots: to show *what changed* between two visits to the same data, we
must keep the previous version. We store the raw resource body (for field-level
diff) plus a content hash (for fast change classification). Synthetic/test data
only in the hackathon — production needs encryption, RBAC, and audit.
"""

import os
import sqlite3
from datetime import datetime, timezone

from backend.fhir import normalize as norm

DB_PATH = os.environ.get("FHIR_DB", os.path.join(os.path.dirname(__file__), "snapshots.db"))


def connect(db_path: str = DB_PATH) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    init_db(conn)
    return conn


def init_db(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS scan_run (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            source TEXT, started_at TEXT, resource_count INTEGER
        );
        CREATE TABLE IF NOT EXISTS resource_snapshot (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            scan_run_id INTEGER,
            resource_key TEXT,
            resource_type TEXT,
            patient_id TEXT,
            version_id TEXT,
            last_updated TEXT,
            content_hash TEXT,
            body TEXT
        );
        CREATE INDEX IF NOT EXISTS idx_snap_scan ON resource_snapshot(scan_run_id);
        """
    )
    conn.commit()


def create_scan_run(conn: sqlite3.Connection, source: str) -> int:
    cur = conn.execute(
        "INSERT INTO scan_run (source, started_at, resource_count) VALUES (?, ?, 0)",
        (source, datetime.now(timezone.utc).isoformat()),
    )
    conn.commit()
    return cur.lastrowid


def save_snapshot(conn: sqlite3.Connection, scan_run_id: int, res: dict) -> None:
    meta = res.get("meta", {}) if isinstance(res.get("meta"), dict) else {}
    conn.execute(
        """INSERT INTO resource_snapshot
           (scan_run_id, resource_key, resource_type, patient_id, version_id,
            last_updated, content_hash, body)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            scan_run_id,
            norm.resource_key(res),
            res.get("resourceType", "Unknown"),
            norm.patient_ref(res),
            meta.get("versionId"),
            meta.get("lastUpdated"),
            norm.content_hash(res),
            norm.stable_json(res),
        ),
    )


def finalize_scan_run(conn: sqlite3.Connection, scan_run_id: int, count: int) -> None:
    conn.execute("UPDATE scan_run SET resource_count = ? WHERE id = ?", (count, scan_run_id))
    conn.commit()


def last_two_scan_ids(conn: sqlite3.Connection) -> tuple[int | None, int | None]:
    rows = conn.execute("SELECT id FROM scan_run ORDER BY id DESC LIMIT 2").fetchall()
    if not rows:
        return None, None
    if len(rows) == 1:
        return None, rows[0]["id"]
    return rows[1]["id"], rows[0]["id"]


def load_snapshot_map(conn: sqlite3.Connection, scan_run_id: int) -> dict[str, sqlite3.Row]:
    rows = conn.execute(
        "SELECT * FROM resource_snapshot WHERE scan_run_id = ?", (scan_run_id,)
    ).fetchall()
    return {row["resource_key"]: row for row in rows}


def reset(conn: sqlite3.Connection) -> None:
    conn.executescript("DELETE FROM resource_snapshot; DELETE FROM scan_run;")
    conn.commit()
