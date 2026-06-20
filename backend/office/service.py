"""
Orchestration for the digital medical office assistant.

Flow:
  queue      -> each request classified by the necessity gate + per-task minutes
  prefill    -> for a physician_review (or form) request: extract from the linked
                synthetic note, build the canonical record, project onto the form;
                clinical-judgement fields are flagged, not invented
  metrics    -> aggregate saved minutes / touchpoints avoided / FTE projection
"""

import os

from backend import llm
from backend.fhir import action_builder
from backend.fhir import writer as fhir_writer
from backend.office import forms, metrics, necessity
from backend.office.data import DEMOGRAPHICS, REQUESTS
from backend.synthetic_data import SAMPLES

_SAMPLE_NOTE = {s["id"]: s["note"] for s in SAMPLES}

_TRUTHY = {"1", "true", "yes", "on"}


def _write_enabled() -> bool:
    return os.environ.get("WRITE_ENABLED", "").strip().lower() in _TRUTHY


def get_queue() -> list[dict]:
    queue = []
    for req in REQUESTS:
        cls = necessity.classify(req["category"])
        m = metrics.per_task(req["category"], cls["route"])
        item = {**req, **cls, "metrics": m,
                "has_form": req["category"] in forms.FORMS}
        if item["has_form"]:
            item["form_title"] = forms.FORMS[req["category"]]["title"]
        queue.append(item)
    return queue


def prefill_request(request_id: str) -> dict:
    req = next((r for r in REQUESTS if r["id"] == request_id), None)
    if not req:
        return {"status": "not_found"}

    cls = necessity.classify(req["category"])
    form_id = req["category"] if req["category"] in forms.FORMS else None
    if not form_id:
        return {"status": "no_form", "request": req, **cls,
                "message": "This request is handled without a form (automate/delegate)."}

    note = _SAMPLE_NOTE.get(req.get("sample_id") or "", "")
    extraction, mode = llm.extract(note, req.get("sample_id")) if note else (None, "none")
    patient_context = DEMOGRAPHICS.get(req["patient_id"], {})

    if extraction is None:
        # No note to extract from — still produce the form with demographics only.
        from backend.schema import EncounterExtraction
        extraction = EncounterExtraction(summary="")

    fl = forms.build_functional_limitations(extraction, patient_context)
    form = forms.prefill_form(form_id, fl)
    return {"status": "ok", "request": req, **cls, "mode": mode,
            "patient_context": patient_context, "form": form}


# Follow-up action per request category — the "task" half of "draft + task".
# (title, owner, due) — illustrative workflow routing, no clinical content.
_FOLLOWUP = {
    "disability_tax_credit": ("Submit signed T2201 and confirm CRA receipt", "admin", "2 weeks"),
    "insurance_std": ("Send completed statement to insurer; confirm receipt", "admin", "1 week"),
    "school_note": ("Send accommodation note to family", "admin", "3 days"),
    "sick_note": ("Issue patient attestation; no physician action", "patient", "same day"),
}
_DEFAULT_FOLLOWUP = ("Complete and route the document", "admin", "1 week")


def approve_request(request_id: str, completed_fields: dict | None = None) -> dict:
    """Physician approves a prefilled form.

    Overlays the physician-completed clinical fields onto the prefilled form,
    then produces a signed-ready draft + a follow-up task. Clinical-judgement
    fields the physician left blank are reported as outstanding — never invented.
    """
    completed_fields = completed_fields or {}
    base = prefill_request(request_id)
    if base.get("status") != "ok":
        return base  # not_found / no_form passthrough

    req = base["request"]
    form = base["form"]
    fields = []
    for f in form["fields"]:
        entered = completed_fields.get(f["id"])
        has_value = entered is not None and str(entered).strip() != ""
        fields.append({**f,
                       "value": entered if has_value else f["value"],
                       "completed_by_physician": has_value and f["needs_physician"]})
    outstanding = [f["label"] for f in fields
                   if f["needs_physician"] and not str(f["value"]).strip()]

    title, owner, due = _FOLLOWUP.get(req["category"], _DEFAULT_FOLLOWUP)
    draft = {"form_id": form["form_id"], "title": form["title"], "fields": fields,
             "complete": not outstanding, "outstanding_fields": outstanding}
    task = {"id": f"task-{request_id}", "title": title, "owner": owner,
            "due": due, "source_request": request_id, "status": "open"}
    result = {"status": "ok", "request": req, "route": base["route"],
              "draft": draft, "follow_up_task": task,
              "metrics": metrics.per_task(req["category"], base["route"])}

    # Close the loop to the EMR: when writes are enabled, also write the follow-up
    # Task and a QuestionnaireResponse built from the completed form. Off by default,
    # leaving the in-memory draft+task response unchanged.
    if _write_enabled():
        result["written"] = _write_back(req, title, owner, fields)
    return result


def _write_back(req: dict, task_title: str, task_owner: str, fields: list[dict]) -> dict:
    """Build + write the follow-up Task and the completed form QuestionnaireResponse.

    Returns the written-resource ids the writer assigned (synthetic in mock mode).
    """
    patient_id = req["patient_id"]
    task_resource = action_builder.build_task(
        patient_id, task_title, owner=task_owner)
    qr_items = [{"linkId": f["id"], "text": f["label"], "value": f["value"]}
                for f in fields]
    qr_resource = action_builder.build_questionnaire_response(
        patient_id, req["category"], qr_items)

    task_result = fhir_writer.create(task_resource)
    qr_result = fhir_writer.create(qr_resource)
    return {
        "mode": task_result.get("mode"),
        "task_id": task_result.get("id"),
        "task_location": task_result.get("location"),
        "questionnaire_response_id": qr_result.get("id"),
        "questionnaire_response_location": qr_result.get("location"),
    }


def project(processed: list[dict]) -> dict:
    """processed: [{category, route}] for requests the physician has actioned."""
    return metrics.project_annual(processed)
