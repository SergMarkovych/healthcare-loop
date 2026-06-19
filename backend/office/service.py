"""
Orchestration for the digital medical office assistant.

Flow:
  queue      -> each request classified by the necessity gate + per-task minutes
  prefill    -> for a physician_review (or form) request: extract from the linked
                synthetic note, build the canonical record, project onto the form;
                clinical-judgement fields are flagged, not invented
  metrics    -> aggregate saved minutes / touchpoints avoided / FTE projection
"""

from backend import llm
from backend.office import forms, metrics, necessity
from backend.office.data import DEMOGRAPHICS, REQUESTS
from backend.synthetic_data import SAMPLES

_SAMPLE_NOTE = {s["id"]: s["note"] for s in SAMPLES}


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


def project(processed: list[dict]) -> dict:
    """processed: [{category, route}] for requests the physician has actioned."""
    return metrics.project_annual(processed)
