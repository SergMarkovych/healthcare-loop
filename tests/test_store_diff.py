"""
Persistence of the scan/diff layer (V4 §12, §14, §21).

Two fixture scans must leave one resource_diff row per resource key on the
*second* scan run, with the right change_status, and a populated diff_json for
the updated MedicationRequest. The scan_run row must be 'complete' with a
completed_at timestamp. Pagination is covered by stubbing a 2-page Bundle on a
fake transport — no network.
"""

import json

import httpx
import pytest

from backend.fhir import client as clientmod
from backend.fhir import store
from backend.fhir.client import FHIRClient


def _diff_rows_by_key(fhir_service):
    fhir_service.run_scan(source="fixtures", which=1)
    fhir_service.run_scan(source="fixtures", which=2)
    conn = store.connect()
    try:
        _prev, curr = store.last_two_scan_ids(conn)
        rows = store.load_resource_diffs(conn, curr)
        return curr, {r["resource_key"]: r for r in rows}, conn
    finally:
        conn.close()


def test_resource_diff_change_statuses(fresh_store):
    _curr, by_key, _conn = _diff_rows_by_key(fresh_store)

    assert by_key["MedicationRequest/med-A1"]["change_status"] == "updated"
    assert by_key["Observation/obs-A2"]["change_status"] == "new"
    assert by_key["Task/task-B1"]["change_status"] == "new"
    assert by_key["Observation/obs-B1"]["change_status"] == "not_returned"
    assert by_key["Observation/obs-A1"]["change_status"] == "unchanged"


def test_updated_row_diff_json_has_dose_change(fresh_store):
    _curr, by_key, _conn = _diff_rows_by_key(fresh_store)

    row = by_key["MedicationRequest/med-A1"]
    assert row["diff_json"], "updated row must carry a populated diff_json"
    changes = json.loads(row["diff_json"])
    dose = [
        c for c in changes
        if "dosageInstruction" in c["path"] and c["change"] == "changed"
    ]
    assert dose, f"expected a dosageInstruction change, got {changes}"
    assert dose[0]["old"] == "500 mg twice daily"
    assert dose[0]["new"] == "1000 mg twice daily"


def test_unchanged_and_new_rows_have_no_diff_json(fresh_store):
    _curr, by_key, _conn = _diff_rows_by_key(fresh_store)
    assert by_key["Observation/obs-A1"]["diff_json"] is None
    assert by_key["Observation/obs-A2"]["diff_json"] is None


def test_diff_rows_carry_snapshot_ids(fresh_store):
    """updated row references both prev and curr snapshot; new references curr only."""
    _curr, by_key, _conn = _diff_rows_by_key(fresh_store)

    upd = by_key["MedicationRequest/med-A1"]
    assert upd["prev_snapshot_id"] is not None
    assert upd["curr_snapshot_id"] is not None

    new = by_key["Observation/obs-A2"]
    assert new["prev_snapshot_id"] is None
    assert new["curr_snapshot_id"] is not None

    gone = by_key["Observation/obs-B1"]
    assert gone["prev_snapshot_id"] is not None
    assert gone["curr_snapshot_id"] is None


def test_scan_run_marked_complete_with_timestamp(fresh_store):
    fresh_store.run_scan(source="fixtures", which=1)
    fresh_store.run_scan(source="fixtures", which=2)
    conn = store.connect()
    try:
        _prev, curr = store.last_two_scan_ids(conn)
        sr = conn.execute(
            "SELECT status, completed_at FROM scan_run WHERE id = ?", (curr,)
        ).fetchone()
    finally:
        conn.close()
    assert sr["status"] == "complete"
    assert sr["completed_at"]


# --- pagination (§14) -------------------------------------------------------

def _bundle(entries, next_url=None):
    b = {"resourceType": "Bundle", "type": "searchset",
         "entry": [{"resource": r} for r in entries]}
    if next_url:
        b["link"] = [{"relation": "next", "url": next_url}]
    return b


def test_search_patients_follows_next_link():
    """A 2-page patient search must return resources from both pages (§14)."""
    page1 = _bundle(
        [{"resourceType": "Patient", "id": "p1"}],
        next_url="https://example.org/baseR4/Patient?_getpages=PAGE2",
    )
    page2 = _bundle([{"resourceType": "Patient", "id": "p2"}])

    calls: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(str(request.url))
        if "PAGE2" in str(request.url):
            return httpx.Response(200, json=page2)
        return httpx.Response(200, json=page1)

    c = FHIRClient("https://example.org/baseR4")
    c._client = httpx.Client(
        base_url="https://example.org/baseR4",
        transport=httpx.MockTransport(handler),
        headers={"Accept": "application/fhir+json"},
    )
    try:
        patients = c.search_patients(count=10)
    finally:
        c.close()

    assert [p["id"] for p in patients] == ["p1", "p2"]
    assert len(calls) == 2
    # the second call must use the server's absolute next URL verbatim
    assert "PAGE2" in calls[1]


def test_pagination_respects_page_cap():
    """A server that always returns a next link stops at MAX_BUNDLE_PAGES."""
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=_bundle(
            [{"resourceType": "Patient", "id": "p"}],
            next_url="https://example.org/baseR4/Patient?_getpages=LOOP",
        ))

    c = FHIRClient("https://example.org/baseR4")
    c._client = httpx.Client(
        base_url="https://example.org/baseR4",
        transport=httpx.MockTransport(handler),
        headers={"Accept": "application/fhir+json"},
    )
    try:
        patients = c.search_patients(count=10)
    finally:
        c.close()

    assert len(patients) == clientmod.MAX_BUNDLE_PAGES


def test_resources_for_patient_records_fetch_error():
    """A failing per-type fetch is surfaced into the errors sink, not swallowed (§21)."""
    def handler(request: httpx.Request) -> httpx.Response:
        if "/Observation" in request.url.path:
            return httpx.Response(500, json={"resourceType": "OperationOutcome"})
        return httpx.Response(200, json=_bundle([]))

    c = FHIRClient("https://example.org/baseR4")
    c._client = httpx.Client(
        base_url="https://example.org/baseR4",
        transport=httpx.MockTransport(handler),
        headers={"Accept": "application/fhir+json"},
    )
    errors: list[dict] = []
    try:
        c.resources_for_patient("p1", ["Condition", "Observation"], errors=errors)
    finally:
        c.close()

    assert len(errors) == 1
    assert errors[0]["resource_type"] == "Observation"
    assert errors[0]["patient_id"] == "p1"


# --- live capability gate (§12) --------------------------------------------

def test_live_scan_capability_failure_marks_run_error(fresh_store, monkeypatch):
    """A failed /metadata marks the scan run errored and returns status=error,
    instead of raising into the caller."""
    from backend.fhir import service as svc

    def boom(self):
        raise httpx.ConnectError("server unreachable")

    monkeypatch.setattr(FHIRClient, "capability", boom)

    result = svc.run_scan(source="live", base_url="https://example.org/baseR4")
    assert result["status"] == "error"
    assert "capability" in result["message"]

    conn = store.connect()
    try:
        sr = conn.execute(
            "SELECT status, error, source_base_url FROM scan_run WHERE id = ?",
            (result["scan_run_id"],),
        ).fetchone()
    finally:
        conn.close()
    assert sr["status"] == "error"
    assert sr["error"]
    assert sr["source_base_url"] == "https://example.org/baseR4"


def test_live_scan_records_capability_and_persists_error_diff(fresh_store, monkeypatch):
    """A live scan records server software/fhirVersion and persists an 'error'
    resource_diff row for a per-type fetch that failed (§12, §21)."""
    from backend.fhir import service as svc

    monkeypatch.setattr(
        FHIRClient, "capability",
        lambda self: {"resourceType": "CapabilityStatement",
                      "fhirVersion": "4.0.1",
                      "software": {"name": "HAPI FHIR", "version": "6.0"}},
    )
    monkeypatch.setattr(
        FHIRClient, "scan",
        lambda self, patient_count=5, types=None: (
            [{"resourceType": "Patient", "id": "p1"}],
            [{"resource_type": "Observation", "patient_id": "p1", "error": "500"}],
        ),
    )

    result = svc.run_scan(source="live", base_url="https://example.org/baseR4")
    assert result["status"] == "ok"

    conn = store.connect()
    try:
        sr = conn.execute(
            "SELECT server_software, fhir_version FROM scan_run WHERE id = ?",
            (result["scan_run_id"],),
        ).fetchone()
        rows = store.load_resource_diffs(conn, result["scan_run_id"])
    finally:
        conn.close()

    assert sr["server_software"] == "HAPI FHIR 6.0"
    assert sr["fhir_version"] == "4.0.1"
    err_rows = [r for r in rows if r["change_status"] == "error"]
    assert len(err_rows) == 1
    assert err_rows[0]["resource_type"] == "Observation"
    assert err_rows[0]["patient_id"] == "p1"
