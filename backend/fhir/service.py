"""
Orchestration layer tying client/fixtures -> snapshot store -> diff -> summary.

Two scan sources:
  - 'fixtures': offline synthetic scans (scan_1.json, scan_2.json). Deterministic,
    works with no network or server — use it to demo the whole pipeline today.
  - 'live': pull from a FHIR R4 base URL (public HAPI, or local HAPI + Synthea).
"""

import json
import os

import httpx

from backend.fhir import diff as diffmod
from backend.fhir import normalize as norm
from backend.fhir import store
from backend.fhir import summarize
from backend.fhir.client import CORE_TYPES, FHIRClient

_FIXTURE_DIR = os.path.join(os.path.dirname(__file__), "fixtures")
FHIR_BASE_URL = os.environ.get("FHIR_BASE_URL", "https://hapi.fhir.org/baseR4")


def load_fixture(which: int) -> list[dict]:
    path = os.path.join(_FIXTURE_DIR, f"scan_{which}.json")
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def _capability_meta(cap: dict) -> tuple[str | None, str | None]:
    """Extract (server software label, fhirVersion) from a CapabilityStatement."""
    sw = cap.get("software") if isinstance(cap.get("software"), dict) else {}
    name, version = sw.get("name"), sw.get("version")
    if name and version:
        server_software = f"{name} {version}"
    else:
        server_software = name or version or None
    return server_software, cap.get("fhirVersion")


def run_scan(source: str = "fixtures", which: int | None = None,
             base_url: str | None = None, patient_count: int = 5) -> dict:
    if source == "live":
        return _run_live_scan(base_url or FHIR_BASE_URL, patient_count)

    which = which if which in (1, 2) else 1
    resources = load_fixture(which)
    label = f"fixtures:scan_{which}"

    conn = store.connect()
    try:
        scan_id = store.create_scan_run(conn, label)
        for res in resources:
            store.save_snapshot(conn, scan_id, res)
        store.finalize_scan_run(conn, scan_id, len(resources))
        _persist_diff_for(conn, scan_id, scan_errors=[])
        patients = _patient_list(resources)
    finally:
        conn.close()

    return {"scan_run_id": scan_id, "source": label,
            "resource_count": len(resources), "patients": patients}


def _run_live_scan(base_url: str, patient_count: int) -> dict:
    client = FHIRClient(base_url)
    label = f"live:{client.base_url}"
    conn = store.connect()
    scan_id = store.create_scan_run(conn, label, source_base_url=client.base_url)
    try:
        # §12: verify the server speaks FHIR (and record what it claims) BEFORE
        # we scan. A failed /metadata marks the run errored and returns a status
        # dict rather than raising into the caller.
        try:
            cap = client.capability()
            server_software, fhir_version = _capability_meta(cap)
            store.record_capability(conn, scan_id, server_software, fhir_version)
        except httpx.HTTPError as err:
            msg = f"capability check failed: {err}"
            store.fail_scan_run(conn, scan_id, msg)
            return {"status": "error", "scan_run_id": scan_id, "source": label, "message": msg}

        try:
            resources, scan_errors = client.scan(patient_count=patient_count, types=CORE_TYPES)
        except httpx.HTTPError as err:
            msg = f"scan failed: {err}"
            store.fail_scan_run(conn, scan_id, msg)
            return {"status": "error", "scan_run_id": scan_id, "source": label, "message": msg}

        for res in resources:
            store.save_snapshot(conn, scan_id, res)
        store.finalize_scan_run(conn, scan_id, len(resources))
        _persist_diff_for(conn, scan_id, scan_errors=scan_errors)
        patients = _patient_list(resources)
    finally:
        conn.close()
        client.close()

    return {"status": "ok", "scan_run_id": scan_id, "source": label,
            "resource_count": len(resources), "patients": patients}


def _patient_list(resources: list[dict]) -> list[dict]:
    return [
        {"id": r.get("id"), "name": _name(r)}
        for r in resources if r.get("resourceType") == "Patient"
    ]


def _persist_diff_for(conn, curr_id: int, scan_errors: list[dict]) -> int:
    """Write one resource_diff row per resource key for this scan run (§12.3).

    Compares the current scan against the immediately-previous one. On the first
    scan there is no predecessor, so every current key is recorded as 'new'.
    Per-type fetch failures (§21) are recorded as 'error' rows so a missing
    resource caused by an API error is distinguishable from a clean 'not_returned'.
    Returns the number of rows written.
    """
    prev_id, _curr = store.last_two_scan_ids(conn)
    curr_map = store.load_snapshot_map(conn, curr_id)
    prev_map = store.load_snapshot_map(conn, prev_id) if prev_id is not None else {}
    classified = diffmod.classify(prev_map, curr_map)

    def _curr_sid(key: str) -> int | None:
        row = curr_map.get(key)
        return row["id"] if row is not None else None

    def _prev_sid(key: str) -> int | None:
        row = prev_map.get(key)
        return row["id"] if row is not None else None

    written = 0
    for status in ("new", "updated", "unchanged", "not_returned"):
        for item in classified.get(status, []):
            key = item["key"]
            diff_json = None
            if status == "updated":
                diff_json = norm.stable_json(item.get("field_changes", []))
            store.save_resource_diff(
                conn, curr_id, key, item.get("resource_type"), item.get("patient_id"),
                status, diff_json=diff_json,
                prev_snapshot_id=_prev_sid(key), curr_snapshot_id=_curr_sid(key),
            )
            written += 1

    for err in scan_errors:
        rtype = err.get("resource_type")
        pid = err.get("patient_id")
        store.save_resource_diff(
            conn, curr_id, f"{rtype}/?patient={pid}", rtype, pid, "error",
            diff_json=norm.stable_json({"error": err.get("error")}),
        )
        written += 1

    conn.commit()
    return written


def diff_last_two() -> dict:
    conn = store.connect()
    try:
        prev_id, curr_id = store.last_two_scan_ids(conn)
        if curr_id is None:
            return {"status": "no_scans"}
        if prev_id is None:
            return {"status": "single_scan", "curr_scan_id": curr_id,
                    "message": "Only one scan so far — run a second scan to see changes."}
        prev_map = store.load_snapshot_map(conn, prev_id)
        curr_map = store.load_snapshot_map(conn, curr_id)
    finally:
        conn.close()
    return {"status": "ok", "prev_scan_id": prev_id, "curr_scan_id": curr_id,
            "diff": diffmod.classify(prev_map, curr_map)}


def list_patients_latest() -> list[dict]:
    conn = store.connect()
    try:
        _, curr_id = store.last_two_scan_ids(conn)
        if curr_id is None:
            return []
        rows = store.load_snapshot_map(conn, curr_id).values()
        return [{"id": json.loads(r["body"]).get("id"), "name": _name(json.loads(r["body"]))}
                for r in rows if r["resource_type"] == "Patient"]
    finally:
        conn.close()


def build_context(patient_id: str) -> dict:
    conn = store.connect()
    try:
        _, curr_id = store.last_two_scan_ids(conn)
        if curr_id is None:
            return {"status": "no_scans"}
        curr_rows = store.load_snapshot_map(conn, curr_id).values()
    finally:
        conn.close()

    current_resources, patient_resource = [], None
    for r in curr_rows:
        body = json.loads(r["body"])
        if r["patient_id"] == patient_id or body.get("id") == patient_id:
            current_resources.append(body)
            if body.get("resourceType") == "Patient":
                patient_resource = body

    full = diff_last_two()
    pdiff = (diffmod.filter_for_patient(full["diff"], patient_id)
             if full.get("status") == "ok"
             else {"new": [], "updated": [], "not_returned": [], "counts": {}})

    board, mode = summarize.summarize(
        patient_id, patient_resource, pdiff, current_resources, CORE_TYPES
    )
    return {"status": "ok", "mode": mode, "board": board}


def current_resources_for_patient(patient_id: str) -> tuple[dict | None, list[dict]]:
    """Latest-scan resources for one patient: (patient_resource, all_resources).

    Returns (None, []) when no scan exists yet — same no_scans signal as build_context.
    """
    conn = store.connect()
    try:
        _, curr_id = store.last_two_scan_ids(conn)
        if curr_id is None:
            return None, []
        curr_rows = store.load_snapshot_map(conn, curr_id).values()
    finally:
        conn.close()

    resources, patient_resource = [], None
    for r in curr_rows:
        body = json.loads(r["body"])
        if r["patient_id"] == patient_id or body.get("id") == patient_id:
            resources.append(body)
            if body.get("resourceType") == "Patient":
                patient_resource = body
    return patient_resource, resources


def _name(patient: dict) -> str:
    names = patient.get("name") or []
    if names:
        n = names[0]
        return f"{' '.join(n.get('given', []))} {n.get('family', '')}".strip() or patient.get("id", "?")
    return patient.get("id", "?")


def reset_store() -> None:
    conn = store.connect()
    try:
        store.reset(conn)
    finally:
        conn.close()
