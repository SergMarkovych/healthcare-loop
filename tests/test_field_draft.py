"""
AI-assisted draft generation for physician-flagged clinical fields.

When a local model is available, flagged clinical-judgement fields are pre-filled
with a *draft* (value + verbatim evidence + confidence), grounded only in the
encounter extraction, marked drafted=True but still role=physician /
needs_physician=True. When no model is available (FORCE_MOCK), behavior is
unchanged: the fields stay blank and undrafted.
"""

from backend.office import field_drafter, service
from backend.schema import (
    Confidence,
    EncounterExtraction,
    Problem,
    ProblemStatus,
)

_DRAFT_JSON = (
    '{"drafts": [{"field_id": "functional_limitations", '
    '"value": "Reduced exertional tolerance; fatigue limits prolonged standing", '
    '"evidence": "reports fatigue and reduced tolerance for exertion", '
    '"confidence": "medium"}]}'
)


def _sample_extraction() -> EncounterExtraction:
    return EncounterExtraction(
        summary="Type 2 diabetes follow-up",
        problems=[Problem(name="Type 2 diabetes", status=ProblemStatus.ongoing,
                          evidence="reports fatigue and reduced tolerance for exertion",
                          confidence=Confidence.high)],
    )


def _fields_by_id(form: dict) -> dict[str, dict]:
    return {f["id"]: f for f in form["fields"]}


def test_draft_clinical_fields_force_mock_returns_empty(monkeypatch):
    monkeypatch.setattr(field_drafter, "FORCE_MOCK", True)

    extraction = _sample_extraction()
    specs = [{"field_id": "functional_limitations", "label": "Functional limitations"}]

    drafts = field_drafter.draft_clinical_fields(extraction, specs)

    assert drafts == {}


def test_draft_clinical_fields_happy_path_stubbed_model(monkeypatch):
    monkeypatch.setattr(field_drafter, "FORCE_MOCK", False)
    monkeypatch.setattr(field_drafter.llm_client, "call_chat",
                        lambda *a, **kw: _DRAFT_JSON)

    extraction = _sample_extraction()
    specs = [{"field_id": "functional_limitations", "label": "Functional limitations"}]

    drafts = field_drafter.draft_clinical_fields(extraction, specs)

    assert "functional_limitations" in drafts
    cell = drafts["functional_limitations"]
    assert cell["value"] == "Reduced exertional tolerance; fatigue limits prolonged standing"
    assert cell["evidence"] == "reports fatigue and reduced tolerance for exertion"
    assert cell["confidence"] == "medium"


def test_prefill_request_overlays_draft_but_keeps_physician_ownership(monkeypatch):
    monkeypatch.setattr(field_drafter, "FORCE_MOCK", False)
    monkeypatch.setattr(field_drafter.llm_client, "call_chat",
                        lambda *a, **kw: _DRAFT_JSON)

    result = service.prefill_request("req-2")

    assert result["status"] == "ok"
    cell = _fields_by_id(result["form"])["functional_limitations"]
    assert cell["value"], "drafted functional_limitations should be non-empty"
    assert cell["drafted"] is True
    assert cell["role"] == "physician"
    assert cell["needs_physician"] is True


def test_prefill_request_no_model_leaves_field_blank_and_undrafted():
    result = service.prefill_request("req-2")

    assert result["status"] == "ok"
    cell = _fields_by_id(result["form"])["functional_limitations"]
    assert cell["value"] == ""
    assert cell.get("drafted", False) is False
    assert cell["role"] == "physician"
