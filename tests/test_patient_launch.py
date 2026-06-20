"""
Per-patient launch wiring (AB#682): the office queue and follow-up note can be
scoped to a single patient, and the board fixtures expose synthetic-C so it
shows up as its own row.

get_queue stays backward-compatible: no patient_id -> the full queue.
"""

import json
from pathlib import Path

from backend.office import service

_FIXTURES = Path(__file__).resolve().parent.parent / "backend" / "fhir" / "fixtures"


def test_get_queue_filters_to_one_patient():
    items = service.get_queue("synthetic-A")
    assert items, "synthetic-A should have requests"
    assert {i["patient_id"] for i in items} == {"synthetic-A"}


def test_get_queue_default_returns_all():
    all_items = service.get_queue()
    assert len(all_items) == len(service.REQUESTS)
    assert {i["patient_id"] for i in all_items} == {"synthetic-A", "synthetic-B", "synthetic-C"}


def test_get_queue_unknown_patient_is_empty():
    assert service.get_queue("nobody") == []


def test_follow_up_note_returns_note_and_name():
    result = service.follow_up_note("synthetic-A")
    assert result["patient_name"] == "Jordan Sample"
    assert result["sample_id"] == "sample-1"
    assert result["note"].strip()


def test_follow_up_note_synthetic_c_uses_req8_sample():
    result = service.follow_up_note("synthetic-C")
    assert result["patient_name"] == "Riley Synthetic"
    assert result["sample_id"] == "sample-5"
    assert "mobility" in result["note"].lower()


def test_follow_up_note_no_sample_is_clean_empty():
    result = service.follow_up_note("nobody")
    assert result == {"patient_id": "nobody", "patient_name": "", "sample_id": None, "note": ""}


def test_office_requests_endpoint_scopes_to_patient(client):
    resp = client.get("/api/office/requests", params={"patient": "synthetic-A"})
    assert resp.status_code == 200
    payload = resp.json()
    assert payload
    assert {i["patient_id"] for i in payload} == {"synthetic-A"}


def test_office_requests_endpoint_default_returns_all(client):
    resp = client.get("/api/office/requests")
    assert resp.status_code == 200
    assert len(resp.json()) == len(service.REQUESTS)


def test_follow_up_note_endpoint_returns_note(client):
    resp = client.get("/api/follow-up/note", params={"patient": "synthetic-A"})
    assert resp.status_code == 200
    payload = resp.json()
    assert payload["note"].strip()
    assert payload["patient_name"] == "Jordan Sample"


def test_follow_up_note_endpoint_no_patient_is_neutral(client):
    resp = client.get("/api/follow-up/note")
    assert resp.status_code == 200
    assert resp.json() == {"note": "", "patient_name": "", "sample_id": None}


def test_fixtures_expose_synthetic_c_patient():
    for name in ("scan_1.json", "scan_2.json"):
        resources = json.loads((_FIXTURES / name).read_text(encoding="utf-8"))
        patients = [r for r in resources
                    if r.get("resourceType") == "Patient" and r.get("id") == "synthetic-C"]
        assert patients, f"synthetic-C Patient missing from {name}"
        assert patients[0]["name"][0]["given"] == ["Riley"]
