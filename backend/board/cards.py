"""
Patient Context Board cards — pure restatement of source-backed FHIR facts.

Safety story (mirrors backend/fhir/summarize.py): these cards may ONLY restate
data the API returned. No diagnosis, no prognosis, no interpretation of whether a
value is good/bad. The deterministic builder composes every item from structured
resources/diff, so it literally cannot invent clinical content; each item carries
a source_reference back to the resource it came from.
"""


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


def _dosage_change(field_changes: list[dict]) -> dict | None:
    for c in field_changes:
        if "dosageInstruction" in c.get("path", "") and c.get("change") == "changed":
            return c
    return None


def _attention_card(current_resources: list[dict], pdiff: dict) -> dict:
    items: list[dict] = []
    current_by_ref = {_ref(r): r for r in current_resources}

    for upd in pdiff.get("updated", []):
        if upd.get("resource_type") != "MedicationRequest":
            continue
        ref = upd["key"]
        res = current_by_ref.get(ref, {})
        med = _codeable_text(res, "medicationCodeableConcept", "medicationReference") or "Medication"
        dose = _dosage_change(upd.get("field_changes") or [])
        if dose:
            text = f"{med} dose changed: {dose['old']} -> {dose['new']}"
        else:
            text = f"{med} order updated: {upd.get('change_count', 0)} field change(s)"
        items.append({
            "text": text,
            "source_reference": ref,
            "evidence": dose or {"change_count": upd.get("change_count", 0)},
        })

    for res in current_resources:
        if res.get("resourceType") != "Observation":
            continue
        label = _codeable_text(res, "code") or _ref(res)
        value = _observation_value(res)
        text = f"Observation on record: {label}"
        if value is not None:
            text += f" = {value}"
        items.append({"text": text, "source_reference": _ref(res)})

    return {"id": "attention", "title": "Worth a glance", "items": items}


def _review_queue_card(current_resources: list[dict], pdiff: dict) -> dict:
    items: list[dict] = []
    counts = pdiff.get("counts", {})

    for it in pdiff.get("new", []):
        items.append({
            "text": f"New since last scan: {it['key']}",
            "source_reference": it["key"],
            "evidence": {"change": "new"},
        })
    for it in pdiff.get("updated", []):
        items.append({
            "text": f"Updated since last scan: {it['key']} ({it.get('change_count', 0)} field change(s))",
            "source_reference": it["key"],
            "evidence": {"change": "updated", "change_count": it.get("change_count", 0)},
        })
    for it in pdiff.get("not_returned", []):
        items.append({
            "text": f"Not returned by current API response: {it['key']}",
            "source_reference": it["key"],
            "evidence": {"change": "not_returned"},
        })

    for res in current_resources:
        if res.get("resourceType") != "Task":
            continue
        status = (res.get("status") or "").lower()
        if status in ("completed", "cancelled", "failed", "rejected", "entered-in-error"):
            continue
        label = _codeable_text(res, "code") or res.get("description") or _ref(res)
        items.append({
            "text": f"Open workflow item: {label}",
            "source_reference": _ref(res),
            "evidence": {"status": res.get("status")},
        })

    title = (
        f"Review queue — {counts.get('new', 0)} new, "
        f"{counts.get('updated', 0)} updated, {counts.get('not_returned', 0)} not returned"
    )
    return {"id": "review_queue", "title": title, "items": items}


def build_cards(patient: dict | None, current_resources: list[dict], pdiff: dict) -> list[dict]:
    return [
        _snapshot_card(patient, current_resources),
        _attention_card(current_resources, pdiff),
        _review_queue_card(current_resources, pdiff),
    ]
