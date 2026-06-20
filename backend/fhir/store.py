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


# V4 §12.1: scan_run columns added after the initial schema shipped. Fresh stores
# get them from CREATE TABLE; existing dev .db files are upgraded by guarded ALTERs.
_SCAN_RUN_ADDED_COLUMNS = (
    ("completed_at", "TEXT"),
    ("source_base_url", "TEXT"),
    ("status", "TEXT"),
    ("error", "TEXT"),
    ("server_software", "TEXT"),
    ("fhir_version", "TEXT"),
)

CHANGE_STATUSES = ("new", "updated", "unchanged", "not_returned", "error")


def init_db(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS scan_run (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            source TEXT, started_at TEXT, resource_count INTEGER,
            completed_at TEXT, source_base_url TEXT, status TEXT, error TEXT,
            server_software TEXT, fhir_version TEXT
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
        CREATE TABLE IF NOT EXISTS resource_diff (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            scan_run_id INTEGER,
            resource_key TEXT,
            resource_type TEXT,
            patient_id TEXT,
            change_status TEXT,
            diff_json TEXT,
            prev_snapshot_id INTEGER,
            curr_snapshot_id INTEGER,
            created_at TEXT
        );
        CREATE INDEX IF NOT EXISTS idx_snap_scan ON resource_snapshot(scan_run_id);
        CREATE INDEX IF NOT EXISTS idx_diff_scan ON resource_diff(scan_run_id);
        """
    )
    _upgrade_scan_run_columns(conn)
    conn.commit()


def _upgrade_scan_run_columns(conn: sqlite3.Connection) -> None:
    """Add §12.1 columns to a scan_run table created by an older schema.

    ALTER TABLE ADD COLUMN raises if the column already exists; we swallow that
    per-column so a fresh CREATE TABLE (which already has them) and an old .db
    both converge to the same shape.
    """
    for name, decl in _SCAN_RUN_ADDED_COLUMNS:
        try:
            conn.execute(f"ALTER TABLE scan_run ADD COLUMN {name} {decl}")
        except sqlite3.OperationalError:
            pass  # column already present


def create_scan_run(conn: sqlite3.Connection, source: str,
                    source_base_url: str | None = None) -> int:
    cur = conn.execute(
        """INSERT INTO scan_run (source, started_at, resource_count, status, source_base_url)
           VALUES (?, ?, 0, 'running', ?)""",
        (source, datetime.now(timezone.utc).isoformat(), source_base_url),
    )
    conn.commit()
    return cur.lastrowid


def record_capability(conn: sqlite3.Connection, scan_run_id: int,
                     server_software: str | None, fhir_version: str | None) -> None:
    conn.execute(
        "UPDATE scan_run SET server_software = ?, fhir_version = ? WHERE id = ?",
        (server_software, fhir_version, scan_run_id),
    )
    conn.commit()


def save_snapshot(conn: sqlite3.Connection, scan_run_id: int, res: dict) -> int:
    meta = res.get("meta", {}) if isinstance(res.get("meta"), dict) else {}
    cur = conn.execute(
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
    return cur.lastrowid


def finalize_scan_run(conn: sqlite3.Connection, scan_run_id: int, count: int) -> None:
    conn.execute(
        """UPDATE scan_run SET resource_count = ?, status = 'complete', completed_at = ?
           WHERE id = ?""",
        (count, datetime.now(timezone.utc).isoformat(), scan_run_id),
    )
    conn.commit()


def fail_scan_run(conn: sqlite3.Connection, scan_run_id: int, error: str) -> None:
    conn.execute(
        """UPDATE scan_run SET status = 'error', error = ?, completed_at = ?
           WHERE id = ?""",
        (error, datetime.now(timezone.utc).isoformat(), scan_run_id),
    )
    conn.commit()


def save_resource_diff(
    conn: sqlite3.Connection,
    scan_run_id: int,
    resource_key: str,
    resource_type: str | None,
    patient_id: str | None,
    change_status: str,
    diff_json: str | None = None,
    prev_snapshot_id: int | None = None,
    curr_snapshot_id: int | None = None,
) -> int:
    if change_status not in CHANGE_STATUSES:
        raise ValueError(f"invalid change_status {change_status!r}; expected one of {CHANGE_STATUSES}")
    cur = conn.execute(
        """INSERT INTO resource_diff
           (scan_run_id, resource_key, resource_type, patient_id, change_status,
            diff_json, prev_snapshot_id, curr_snapshot_id, created_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            scan_run_id, resource_key, resource_type, patient_id, change_status,
            diff_json, prev_snapshot_id, curr_snapshot_id,
            datetime.now(timezone.utc).isoformat(),
        ),
    )
    return cur.lastrowid


def load_resource_diffs(conn: sqlite3.Connection, scan_run_id: int) -> list[sqlite3.Row]:
    return conn.execute(
        "SELECT * FROM resource_diff WHERE scan_run_id = ? ORDER BY resource_key",
        (scan_run_id,),
    ).fetchall()


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
    conn.executescript(
        "DELETE FROM resource_diff; DELETE FROM resource_snapshot; DELETE FROM scan_run;"
    )
    conn.commit()
