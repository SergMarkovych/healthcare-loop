"""
Patient Context Board cards — pure restatement of source-backed FHIR facts.

Canonical V4 5-card shape (docs/design/v4-board-ui.md §3), in this order:
  1. patient_snapshot  — demographics, active Conditions, current Medications, last visit.
  2. new_updated       — one item per pdiff.new / pdiff.updated; updated items show each
                         field change as previous -> current, with a best-effort query hint.
  3. open_workflow     — open Task/ServiceRequest items (same status logic as summarize).
  4. limitations       — not_returned keys + requested-but-absent resource types.
  5. source_references — the deduped ResourceType/id provenance list across the board.

Safety story (mirrors backend/fhir/summarize.py and backend/fhir/rules.py): these cards may
ONLY restate data the API returned. No diagnosis, no prognosis, no interpretation of whether a
value is good/bad. The deterministic builder composes every item from structured
resources/diff, so it literally cannot invent clinical content; each item carries a
source_reference back to the resource it came from.
"""

from backend.fhir import summarize as summarizemod
from backend.fhir.client import CORE_TYPES


def _ref(res: dict) -> str:
    return f"{res.get('resourceType', 'Unknown')}/{res.get('id', '?')}"


def _display_name(patient: dict | None) -> str:
    if not patient:
        return "Unknown patient"
    names = patient.get("name") or []
    if names:
        n = names[0]
        given = " ".join(n.get("given", []))
        return f"{given} {n.get('family', '')}".strip() or patient.get("id", "Unknown")
    return patient.get("id", "Unknown")


def _codeable_text(res: dict, *fields: str) -> str | None:
    for field in fields:
        val = res.get(field)
        if isinstance(val, dict):
            text = val.get("text")
            if text:
                return text
            for coding in val.get("coding") or []:
                if isinstance(coding, dict) and (coding.get("display") or coding.get("code")):
                    return coding.get("display") or coding.get("code")
        elif isinstance(val, str) and val:
            return val
    return None


def _is_active(res: dict) -> bool:
    cs = res.get("clinicalStatus")
    if isinstance(cs, dict):
        for coding in cs.get("coding") or []:
            if isinstance(coding, dict) and (coding.get("code") or "").lower() == "active":
                return True
        if (cs.get("text") or "").lower() == "active":
            return True
    return (res.get("status") or "").lower() == "active"


def _observation_value(res: dict) -> str | None:
    vq = res.get("valueQuantity")
    if isinstance(vq, dict) and vq.get("value") is not None:
        unit = vq.get("unit") or ""
        return f"{vq['value']} {unit}".strip()
    if isinstance(res.get("valueString"), str):
        return res["valueString"]
    cc = res.get("valueCodeableConcept")
    if isinstance(cc, dict) and cc.get("text"):
        return cc["text"]
    return None


def _encounter_when(res: dict) -> str | None:
    period = res.get("period")
    if isinstance(period, dict):
        return period.get("start") or period.get("end")
    return None


def _type_of_ref(ref: str) -> str:
    """ResourceType from a 'ResourceType/id' key (best-effort)."""
    return ref.split("/", 1)[0] if "/" in ref else ref


def _source_query(ref: str, patient_id: str) -> str:
    """Best-effort source-API query hint. The exact query isn't persisted, so this
    reconstructs the canonical patient-scoped search the resource would have come from."""
    return f"{_type_of_ref(ref)}?patient={patient_id}"


# --- Card 1: patient snapshot --------------------------------------------------

def _snapshot_card(patient: dict | None, current_resources: list[dict]) -> dict:
    items: list[dict] = []
    if patient:
        items.append({
            "text": f"Name: {_display_name(patient)}",
            "source_reference": _ref(patient),
        })
        if patient.get("gender"):
            items.append({"text": f"Gender: {patient['gender']}", "source_reference": _ref(patient)})
        if patient.get("birthDate"):
            items.append({"text": f"Date of birth: {patient['birthDate']}", "source_reference": _ref(patient)})

    for res in current_resources:
        rt = res.get("resourceType")
        if rt == "Condition" and _is_active(res):
            label = _codeable_text(res, "code") or _ref(res)
            items.append({"text": f"Active condition: {label}", "source_reference": _ref(res)})

    for res in current_resources:
        if res.get("resourceType") == "MedicationRequest":
            med = _codeable_text(res, "medicationCodeableConcept", "medicationReference") or "Medication"
            dosages = [
                d.get("text") for d in (res.get("dosageInstruction") or [])
                if isinstance(d, dict) and d.get("text")
            ]
            text = f"Medication: {med}"
            if dosages:
                text += f" — {'; '.join(dosages)}"
            item = {"text": text, "source_reference": _ref(res)}
            if res.get("status"):
                item["evidence"] = f"status: {res['status']}"
            items.append(item)

    encounters = [r for r in current_resources if r.get("resourceType") == "Encounter"]
    if encounters:
        last = max(encounters, key=lambda r: (_encounter_when(r) or ""))
        when = _encounter_when(last)
        text = "Last visit" + (f": {when}" if when else "")
        item = {"text": text, "source_reference": _ref(last)}
        if last.get("status"):
            item["evidence"] = f"status: {last['status']}"
        items.append(item)

    return {"id": "patient_snapshot", "title": "Patient snapshot", "items": items}


# --- Card 2: new / updated -----------------------------------------------------

def _new_updated_card(current_resources: list[dict], pdiff: dict, patient_id: str) -> dict:
    items: list[dict] = []
    current_by_ref = {_ref(r): r for r in current_resources}

    for it in pdiff.get("new", []):
        ref = it["key"]
        rt = it.get("resource_type") or _type_of_ref(ref)
        items.append({
            "text": f"New {rt} returned since last scan.",
            "source_reference": ref,
            "source_query": _source_query(ref, patient_id),
            "change_status": "new",
            "evidence": {"change": "new"},
        })

    for it in pdiff.get("updated", []):
        ref = it["key"]
        rt = it.get("resource_type") or _type_of_ref(ref)
        res = current_by_ref.get(ref, {})
        label = (
            _codeable_text(res, "code", "medicationCodeableConcept", "medicationReference")
            or rt
        )
        field_changes = it.get("field_changes") or []
        changes: list[dict] = []
        for c in field_changes:
            changes.append({
                "path": c.get("path"),
                "previous": c.get("old"),
                "current": c.get("new"),
                "change": c.get("change"),
            })
        change_phrases = [
            f"{c['path']}: {c['previous']!r} -> {c['current']!r}"
            for c in changes if c.get("change") == "changed"
        ]
        if change_phrases:
            text = f"{label} updated — " + "; ".join(change_phrases)
        else:
            text = f"{label} updated: {it.get('change_count', len(field_changes))} field change(s)."
        items.append({
            "text": text,
            "source_reference": ref,
            "source_query": _source_query(ref, patient_id),
            "change_status": "updated",
            "evidence": {"change": "updated", "change_count": it.get("change_count", len(field_changes))},
            "changes": changes,
        })

    return {"id": "new_updated", "title": "New / updated", "items": items}


# --- Card 3: open workflow -----------------------------------------------------

def _open_workflow_card(current_resources: list[dict]) -> dict:
    items: list[dict] = []
    for res in current_resources:
        if res.get("resourceType") not in ("Task", "ServiceRequest"):
            continue
        status = (res.get("status") or "").lower()
        if status not in summarizemod._WORKFLOW_OPEN:
            continue
        label = _codeable_text(res, "code") or res.get("description") or _ref(res)
        items.append({
            "text": f"Open workflow item: {label}",
            "source_reference": _ref(res),
            "evidence": {"status": res.get("status")},
        })
    return {"id": "open_workflow", "title": "Open workflow", "items": items}


# --- Card 4: limitations -------------------------------------------------------

_LIMITATION_NOTE = "absent from the API response — reported not-returned, not deleted"


def _limitations_card(
    patient: dict | None, current_resources: list[dict], pdiff: dict, patient_id: str
) -> dict:
    # Reuse summarize.build_board's limitations computation rather than reinventing it.
    sub_board = summarizemod.build_board(
        patient_id, patient, pdiff, current_resources, CORE_TYPES
    )

    items: list[dict] = []

    for it in pdiff.get("not_returned", []):
        ref = it["key"]
        rt = it.get("resource_type") or _type_of_ref(ref)
        items.append({
            "text": f"{ref} ({rt}) {_LIMITATION_NOTE}.",
            "source_reference": ref,
            "evidence": {"change": "not_returned"},
        })

    present_types = {r.get("resourceType") for r in current_resources}
    not_returned_types = sorted(t for t in CORE_TYPES if t not in present_types)
    for t in not_returned_types:
        items.append({
            "text": f"{t}: requested resource type {_LIMITATION_NOTE}.",
            "source_reference": None,
            "evidence": {"requested_type_absent": t},
        })

    card = {"id": "limitations", "title": "Not returned & API limitations", "items": items}
    card["data_source_limitations"] = sub_board["data_source_limitations"]
    return card


# --- Card 5: source references -------------------------------------------------

def _source_references_card(card_list: list[dict], patient_id: str) -> dict:
    refs = sorted({
        item["source_reference"]
        for card in card_list
        for item in card["items"]
        if item.get("source_reference")
    })
    items = [
        {
            "text": ref,
            "source_reference": ref,
            "source_query": _source_query(ref, patient_id),
        }
        for ref in refs
    ]
    return {"id": "source_references", "title": "Source references", "items": items}


def build_cards(patient: dict | None, current_resources: list[dict], pdiff: dict) -> list[dict]:
    patient_id = (patient or {}).get("id") or _patient_id_from(current_resources, pdiff)

    snapshot = _snapshot_card(patient, current_resources)
    new_updated = _new_updated_card(current_resources, pdiff, patient_id)
    open_workflow = _open_workflow_card(current_resources)
    limitations = _limitations_card(patient, current_resources, pdiff, patient_id)

    source_refs = _source_references_card(
        [snapshot, new_updated, open_workflow, limitations], patient_id
    )

    return [snapshot, new_updated, open_workflow, limitations, source_refs]


def _patient_id_from(current_resources: list[dict], pdiff: dict) -> str:
    for grp in ("new", "updated", "not_returned"):
        for it in pdiff.get(grp, []):
            if it.get("patient_id"):
                return it["patient_id"]
    for r in current_resources:
        subj = r.get("subject") or r.get("for") or {}
        ref = subj.get("reference") if isinstance(subj, dict) else None
        if isinstance(ref, str) and "/" in ref:
            return ref.split("/")[-1]
    return "unknown"
