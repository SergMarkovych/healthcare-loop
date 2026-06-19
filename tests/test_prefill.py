"""
Disability Tax Credit prefill — the "AI invents nothing for clinical fields"
safety invariant.

Auto fields (patient_name, date_of_birth, diagnosis) come back populated with
evidence and role=auto/needs_physician=false. Clinical-judgement fields
(onset_date, functional_limitations, prognosis) come back EMPTY with role=physician
/ needs_physician=true — no fabricated value.
"""

from backend.office import forms, service


def _fields_by_id(form: dict) -> dict[str, dict]:
    return {f["id"]: f for f in form["fields"]}


def test_dtc_prefill_endpoint_auto_vs_clinical(client):
    resp = client.post("/api/office/prefill", json={"request_id": "req-2"})
    assert resp.status_code == 200
    payload = resp.json()
    assert payload["status"] == "ok"

    form = payload["form"]
    assert form["form_id"] == "disability_tax_credit"
    fields = _fields_by_id(form)

    for key in ("patient_name", "date_of_birth", "diagnosis"):
        cell = fields[key]
        assert cell["value"], f"{key} should be auto-filled, got empty"
        assert cell["evidence"], f"{key} should carry an evidence snippet"
        assert cell["role"] == "auto"
        assert cell["needs_physician"] is False

    for key in ("onset_date", "functional_limitations", "prognosis"):
        cell = fields[key]
        assert cell["value"] == "", f"{key} must NOT be fabricated, got {cell['value']!r}"
        assert cell["role"] == "physician"
        assert cell["needs_physician"] is True


def test_dtc_prefill_known_values():
    result = service.prefill_request("req-2")
    fields = _fields_by_id(result["form"])
    assert fields["patient_name"]["value"] == "Jordan Sample"
    assert fields["date_of_birth"]["value"] == "1968-03-12"
    assert fields["diagnosis"]["value"] == "Type 2 diabetes"


def test_build_functional_limitations_clinical_fields_empty():
    from backend.schema import (
        Confidence,
        EncounterExtraction,
        Problem,
        ProblemStatus,
    )

    extraction = EncounterExtraction(
        summary="x",
        problems=[Problem(name="Type 2 diabetes", status=ProblemStatus.ongoing,
                          evidence="dx snippet", confidence=Confidence.high)],
    )
    fl = forms.build_functional_limitations(
        extraction, {"name": "Jordan Sample", "birthDate": "1968-03-12"}
    )
    for key in ("onset_date", "functional_limitations", "prognosis"):
        assert fl[key]["value"] == ""
        assert fl[key]["needs_physician"] is True
        assert fl[key]["role"] == "physician"
