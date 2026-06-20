"""
Tests for the deterministic, source-backed rules engine (backend.fhir.rules).

These drive the two synthetic fixture scans through the real FHIR service, then
evaluate the §15 rules per patient and assert on the exact flags produced. The
hard safety invariant — never any clinical interpretation/recommendation, and no
forbidden clinical wording in any message — is asserted on every flag.
"""

from backend.fhir import diff as diffmod
from backend.fhir import rules
from backend.fhir.summarize import _FORBIDDEN


def _evaluate_patient(fhir_service, patient_id: str) -> list[dict]:
    """Patient-filtered diff + current resources -> rules.evaluate flags."""
    full = fhir_service.diff_last_two()
    assert full.get("status") == "ok", full
    pdiff = diffmod.filter_for_patient(full["diff"], patient_id)
    _patient, current_resources = fhir_service.current_resources_for_patient(patient_id)
    return rules.evaluate(pdiff, current_resources, patient_id)


def _by_rule(flags: list[dict], rule_id: str) -> list[dict]:
    return [f for f in flags if f["ruleId"] == rule_id]


def _find(flags: list[dict], rule_id: str, source: str) -> dict | None:
    for f in flags:
        if f["ruleId"] == rule_id and f["source"] == source:
            return f
    return None


def _run_two_scans(fhir_service) -> None:
    fhir_service.run_scan(source="fixtures", which=1)
    fhir_service.run_scan(source="fixtures", which=2)


def test_resource_updated_medication_dose_change(fresh_store):
    _run_two_scans(fresh_store)
    flags = _evaluate_patient(fresh_store, "synthetic-A")

    flag = _find(flags, "resource_updated", "MedicationRequest/med-A1")
    assert flag is not None, _by_rule(flags, "resource_updated")
    assert flag["category"] == "data_change"
    assert flag["changeStatus"] == "updated"
    # Message restates the field change verbatim: 500 -> 1000.
    assert "dosageInstruction[0].text" in flag["message"]
    assert "500 mg twice daily" in flag["message"]
    assert "1000 mg twice daily" in flag["message"]
    assert "->" in flag["message"]


def test_new_resource_found_observation(fresh_store):
    _run_two_scans(fresh_store)
    flags = _evaluate_patient(fresh_store, "synthetic-A")

    flag = _find(flags, "new_resource_found", "Observation/obs-A2")
    assert flag is not None, _by_rule(flags, "new_resource_found")
    assert flag["category"] == "data_change"
    assert flag["changeStatus"] == "new"
    assert "New Observation returned since last scan." == flag["message"]


def test_resource_not_returned_observation_patient_b(fresh_store):
    _run_two_scans(fresh_store)
    flags = _evaluate_patient(fresh_store, "synthetic-B")

    flag = _find(flags, "resource_not_returned", "Observation/obs-B1")
    assert flag is not None, _by_rule(flags, "resource_not_returned")
    assert flag["category"] == "data_availability"
    assert flag["changeStatus"] == "not_returned"
    assert "absence is not deletion" in flag["message"]


def test_active_workflow_item_task_patient_b(fresh_store):
    _run_two_scans(fresh_store)
    flags = _evaluate_patient(fresh_store, "synthetic-B")

    flag = _find(flags, "active_workflow_item", "Task/task-B1")
    assert flag is not None, _by_rule(flags, "active_workflow_item")
    assert flag["category"] == "workflow"
    assert flag["changeStatus"] == "requested"
    assert "requested" in flag["message"]
    assert "Patient to bring home blood pressure log to next visit" in flag["message"]


def test_no_clinical_interpretation_or_recommendation_ever(fresh_store):
    _run_two_scans(fresh_store)
    for patient_id in ("synthetic-A", "synthetic-B"):
        flags = _evaluate_patient(fresh_store, patient_id)
        assert flags, f"expected flags for {patient_id}"
        for f in flags:
            assert f["clinicalInterpretation"] is None, f
            assert f["treatmentRecommendation"] is None, f


def test_no_forbidden_clinical_wording_in_messages(fresh_store):
    _run_two_scans(fresh_store)
    for patient_id in ("synthetic-A", "synthetic-B"):
        flags = _evaluate_patient(fresh_store, patient_id)
        for f in flags:
            low = f["message"].lower()
            hits = [term for term in _FORBIDDEN if term in low]
            assert not hits, f"forbidden wording {hits} in {f['message']!r}"


def test_every_flag_has_exact_shape(fresh_store):
    _run_two_scans(fresh_store)
    expected_keys = {
        "ruleId", "category", "changeStatus", "message", "source",
        "clinicalInterpretation", "treatmentRecommendation",
    }
    for patient_id in ("synthetic-A", "synthetic-B"):
        for f in _evaluate_patient(fresh_store, patient_id):
            assert set(f) == expected_keys, f
            assert isinstance(f["source"], str) and "/" in f["source"]
