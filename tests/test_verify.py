"""
Verification gate (Work Stream 5, ADR-0005) — the safety invariant for office forms:
every value on a form must trace to evidence or carry an explicit not-invented flag,
and required fields must be present.

Deterministic, offline (FORCE_MOCK=1 via conftest). Cases run over forms built from
the live forms.prefill_form shape, plus one endpoint round-trip.
"""

from backend.office import forms, verifier
from backend.office.forms import prefill_form
from backend.schema import (
    Confidence,
    EncounterExtraction,
    Problem,
    ProblemStatus,
)


def _grounded_form(form_id: str) -> dict:
    """A prefill_form-shaped dict where every field of `form_id` carries a value + evidence."""
    fields = []
    for key in forms.FORMS[form_id]["fields"]:
        fields.append({
            "id": key,
            "label": forms.FIELD_LABELS.get(key, key),
            "value": f"grounded {key}",
            "role": "auto",
            "confidence": "high",
            "evidence": f"note snippet for {key}",
            "needs_physician": False,
            "drafted": False,
        })
    return {"form_id": form_id, "title": forms.FORMS[form_id]["title"], "fields": fields}


def test_verify_fully_grounded_form_passes():
    form = _grounded_form("school_note")
    req = verifier.from_form("school_note", form)
    result = verifier.verify(req)

    assert result.status == "pass"
    assert result.ungrounded == []
    assert result.missing_required == []


def test_verify_fabricated_field_is_ungrounded():
    form = _grounded_form("school_note")
    fab = next(f for f in form["fields"] if f["id"] == "diagnosis")
    fab["value"] = "Sensorineural hearing loss"
    fab["evidence"] = ""
    fab["needs_physician"] = False

    req = verifier.from_form("school_note", form)
    result = verifier.verify(req)

    assert result.status == "flag"
    assert "diagnosis" in result.ungrounded
    assert "diagnosis" not in result.missing_required
    assert any("diagnosis" in n for n in result.notes)


def test_verify_missing_required_data_field_is_reported():
    # No problems extracted -> diagnosis (required DTC auto-DATA field, not a
    # judgment field) comes back empty: a genuine auto-DATA gap the gate must flag.
    extraction = EncounterExtraction(summary="x")
    fl = forms.build_functional_limitations(
        extraction, {"name": "Jordan Sample", "birthDate": "1968-03-12"}
    )
    form = prefill_form("disability_tax_credit", fl)

    req = verifier.from_form("disability_tax_credit", form)
    result = verifier.verify(req)

    assert result.status == "flag"
    assert "diagnosis" in result.missing_required
    dx_field = next(f for f in req.fields if f.name == "diagnosis")
    assert dx_field.required is True
    assert dx_field.value is None
    assert dx_field.not_invented_flag is False


def test_verify_empty_judgment_fields_pass_not_missing():
    # A clean draft: auto-DATA fields grounded, the only empty required fields are
    # not-invented judgment fields (the MD's to fill) -> status "pass", and those
    # fields are NOT reported as missing. This is the gate's whole point.
    extraction = EncounterExtraction(
        summary="x",
        problems=[Problem(name="Type 2 diabetes", status=ProblemStatus.ongoing,
                          evidence="dx snippet", confidence=Confidence.high)],
    )
    fl = forms.build_functional_limitations(
        extraction, {"name": "Jordan Sample", "birthDate": "1968-03-12"}
    )
    form = prefill_form("disability_tax_credit", fl)

    req = verifier.from_form("disability_tax_credit", form)
    judgment = [f for f in req.fields
                if f.required and f.value is None and f.not_invented_flag]
    assert judgment, "expected at least one empty required judgment field in this draft"

    result = verifier.verify(req)

    assert result.status == "pass"
    assert result.missing_required == []
    for f in judgment:
        assert f.name not in result.missing_required


def test_verify_endpoint_is_server_derived(client):
    # The endpoint takes a request_id and derives the verdict from the server's own
    # prefill output. A caller cannot forge a "pass" by supplying its own fields:
    # there is no field input to forge.
    from backend.office import service

    rid = next(r["id"] for r in client.get("/api/office/requests").json()
               if r.get("has_form"))
    resp = client.post("/api/office/verify", json={"request_id": rid})
    assert resp.status_code == 200
    payload = resp.json()

    assert payload["status"] in ("pass", "flag")
    assert isinstance(payload["ungrounded"], list)
    assert isinstance(payload["missing_required"], list)
    # identical to the gate computed during prefill -> proves the same server-derived path
    assert payload == service.prefill_request(rid)["verification"]
