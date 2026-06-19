"""
Safety post-filter — backend.fhir.summarize._passes_safety.

Clinical-decision wording (diagnose / prescribe / interpret a value) is rejected;
benign source-restating text passes. When rejected, the deterministic summary is
used instead of the model text (fail safe, not fail open).
"""

import pytest

from backend.fhir import summarize


@pytest.mark.parametrize(
    "text",
    [
        "The patient's diabetes is uncontrolled and the dose should be increased.",
        "Recommend starting an ACE inhibitor for blood pressure.",
        "The A1c value is abnormal and concerning.",
        "Will prescribe an additional agent and order labs.",
    ],
)
def test_clinical_wording_rejected(text):
    assert summarize._passes_safety(text) is False


@pytest.mark.parametrize(
    "text",
    [
        "Since the previous scan: 2 new, 1 updated, 1 not returned.",
        "New Task returned (Task/task-B1).",
        "MedicationRequest updated (MedicationRequest/med-A1): 1 field change(s).",
        "Open workflow item: Patient to bring home blood pressure log (status: requested).",
    ],
)
def test_benign_restatement_passes(text):
    assert summarize._passes_safety(text) is True


def test_summarize_uses_deterministic_text_under_force():
    board = {
        "snapshot": {"name": "Jordan Sample", "gender": "male", "birthDate": "1968-03-12"},
        "changes": {
            "counts": {"new": 2, "updated": 1, "not_returned": 1},
            "new": [{"resource_type": "Task", "key": "Task/task-B1"}],
            "updated": [{"resource_type": "MedicationRequest", "key": "MedicationRequest/med-A1",
                         "change_count": 1}],
            "not_returned": [{"resource_type": "Observation", "key": "Observation/obs-B1"}],
        },
        "open_workflow_items": [],
    }
    text = summarize.deterministic_text(board)
    assert summarize._passes_safety(text) is True
    assert "2 new, 1 updated, 1 not returned" in text
    assert "diagnos" not in text.lower()
    assert "prescrib" not in text.lower()
