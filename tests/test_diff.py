"""
Change detection over fixtures scan_1 vs scan_2.

Expected: 2 new, 1 updated, 1 not_returned, 7 unchanged. The one updated item is
MedicationRequest med-A1 (dosageInstruction 500 -> 1000). The content-hash logic
treats obs-A1 — whose meta.versionId/lastUpdated changed but whose clinical
content is identical — as unchanged.
"""

import json
from pathlib import Path

import pytest

from backend.fhir import diff as diffmod
from backend.fhir import normalize as norm

_FIXTURES = Path(__file__).resolve().parent.parent / "backend" / "fhir" / "fixtures"


def _run_two_scans(fhir_service):
    fhir_service.run_scan(source="fixtures", which=1)
    fhir_service.run_scan(source="fixtures", which=2)
    result = fhir_service.diff_last_two()
    assert result["status"] == "ok"
    return result["diff"]


def test_diff_counts(fresh_store):
    diff = _run_two_scans(fresh_store)
    assert diff["counts"] == {"new": 2, "updated": 1, "unchanged": 7, "not_returned": 1}


def test_diff_new_and_not_returned_keys(fresh_store):
    diff = _run_two_scans(fresh_store)
    new_keys = {i["key"] for i in diff["new"]}
    not_returned_keys = {i["key"] for i in diff["not_returned"]}
    assert new_keys == {"Observation/obs-A2", "Task/task-B1"}
    assert not_returned_keys == {"Observation/obs-B1"}


def test_updated_item_is_med_a1_dose_change(fresh_store):
    diff = _run_two_scans(fresh_store)
    assert len(diff["updated"]) == 1
    updated = diff["updated"][0]
    assert updated["key"] == "MedicationRequest/med-A1"
    assert updated["resource_type"] == "MedicationRequest"

    dose_changes = [
        c for c in updated["field_changes"]
        if "dosageInstruction" in c["path"] and c["change"] == "changed"
    ]
    assert dose_changes, f"expected a dosageInstruction change, got {updated['field_changes']}"
    change = dose_changes[0]
    assert change["old"] == "500 mg twice daily"
    assert change["new"] == "1000 mg twice daily"


def test_content_hash_ignores_volatile_meta(fresh_store):
    """obs-A1 changed versionId 1->3 + lastUpdated but identical content => unchanged."""
    diff = _run_two_scans(fresh_store)
    unchanged_keys = {i["key"] for i in diff["unchanged"]}
    assert "Observation/obs-A1" in unchanged_keys

    scan_1 = {norm.resource_key(r): r for r in json.loads((_FIXTURES / "scan_1.json").read_text())}
    scan_2 = {norm.resource_key(r): r for r in json.loads((_FIXTURES / "scan_2.json").read_text())}
    obs_1, obs_2 = scan_1["Observation/obs-A1"], scan_2["Observation/obs-A1"]
    assert obs_1["meta"]["versionId"] != obs_2["meta"]["versionId"]
    assert obs_1["meta"]["lastUpdated"] != obs_2["meta"]["lastUpdated"]
    assert norm.content_hash(obs_1) == norm.content_hash(obs_2)
