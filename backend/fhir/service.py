"""
Orchestration layer tying client/fixtures -> snapshot store -> diff -> summary.

Two scan sources:
  - 'fixtures': offline synthetic scans (scan_1.json, scan_2.json). Deterministic,
    works with no network or server — use it to demo the whole pipeline today.
  - 'live': pull from a FHIR R4 base URL (public HAPI, or local HAPI + Synthea).
"""

import json
import os

from backend.fhir import diff as diffmod
from backend.fhir import store
from backend.fhir import summarize
from backend.fhir.client import CORE_TYPES, FHIRClient

_FIXTURE_DIR = os.path.join(os.path.dirname(__file__), "fixtures")
FHIR_BASE_URL = os.environ.get("FHIR_BASE_URL", "https://hapi.fhir.org/baseR4")


def load_fixture(which: int) -> list[dict]:
    path = os.path.join(_FIXTURE_DIR, f"scan_{which}.json")
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def run_scan(source: str = "fixtures", which: int | None = None,
             base_url: str | None = None, patient_count: int = 5) -> dict:
    if source == "live":
        client = FHIRClient(base_url or FHIR_BASE_URL)
        try:
            resources = client.scan(patient_count=patient_count, types=CORE_TYPES)
            label = f"live:{client.base_url}"
        finally:
            client.close()
    else:
        which = which if which in (1, 2) else 1
        resources = load_fixture(which)
        label = f"fixtures:scan_{which}"

    conn = store.connect()
    try:
        scan_id = store.create_scan_run(conn, label)
        for res in resources:
            store.save_snapshot(conn, scan_id, res)
        store.finalize_scan_run(conn, scan_id, len(resources))
        patients = [
            {"id": r.get("id"), "name": _name(r)}
            for r in resources if r.get("resourceType") == "Patient"
        ]
    finally:
        conn.close()

    return {"scan_run_id": scan_id, "source": label,
            "resource_count": len(resources), "patients": patients}


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
