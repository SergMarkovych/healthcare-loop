"""
Deterministic, source-backed rules engine (canonical V4 spec §15).

This is a pure restatement layer over the structured patient diff and the current
resource snapshot. It emits *data* and *workflow* flags only — it never diagnoses,
prescribes, interprets severity, or recommends treatment.

Safety story (mirrors backend/fhir/summarize.py and backend/board/cards.py):
  - Every flag is composed deterministically from structured diff/resource fields,
    so it literally cannot invent clinical content.
  - Each flag carries a `source` reference back to the resource it came from.
  - `clinicalInterpretation` and `treatmentRecommendation` are ALWAYS None.
  - As a belt-and-braces guard, every emitted message is checked against
    summarize's forbidden-wording list; a hit raises (a bug in this module, not a
    runtime condition) rather than silently shipping clinical wording.

Flag shape (exact):
    {
      "ruleId": str,
      "category": str,
      "changeStatus": str,
      "message": str,
      "source": "ResourceType/id",
      "clinicalInterpretation": None,
      "treatmentRecommendation": None,
    }
"""

from backend.fhir.summarize import _FORBIDDEN

# Statuses that mean "this workflow item is still open / awaiting action".
_WORKFLOW_OPEN = {"open", "active", "requested", "in-progress", "on-hold",
                  "received", "accepted", "ready", "draft"}
_WORKFLOW_TYPES = ("Task", "ServiceRequest")


def _ref(res: dict) -> str:
    return f"{res.get('resourceType', 'Unknown')}/{res.get('id', '?')}"


def _assert_neutral(message: str) -> None:
    """Belt-and-braces: a flag message must never carry clinical-judgement wording.

    A hit here is a programming error in this module (we compose every message from
    structured fields), so we fail loud rather than ship interpretive text.
    """
    low = message.lower()
    for term in _FORBIDDEN:
        if term in low:
            raise ValueError(
                f"rules.evaluate produced a message containing forbidden wording "
                f"{term!r}: {message!r}"
            )


def _flag(rule_id: str, category: str, change_status: str, message: str,
          source: str) -> dict:
    _assert_neutral(message)
    return {
        "ruleId": rule_id,
        "category": category,
        "changeStatus": change_status,
        "message": message,
        "source": source,
        "clinicalInterpretation": None,
        "treatmentRecommendation": None,
    }


def _field_change_phrase(change: dict) -> str:
    """Restate a single field change verbatim, no interpretation."""
    path = change.get("path", "?")
    kind = change.get("change")
    if kind == "added":
        return f"{path} added: {change.get('new')!r}."
    if kind == "removed":
        return f"{path} removed (was {change.get('old')!r})."
    return f"{path} changed: {change.get('old')!r} -> {change.get('new')!r}."


def _new_resource_flags(pdiff: dict) -> list[dict]:
    out: list[dict] = []
    for item in pdiff.get("new", []):
        rt = item.get("resource_type", "resource")
        out.append(_flag(
            rule_id="new_resource_found",
            category="data_change",
            change_status="new",
            message=f"New {rt} returned since last scan.",
            source=item["key"],
        ))
    return out


def _resource_updated_flags(pdiff: dict) -> list[dict]:
    out: list[dict] = []
    for item in pdiff.get("updated", []):
        rt = item.get("resource_type", "resource")
        changes = item.get("field_changes") or []
        if changes:
            phrases = " ".join(
                f"{rt} field {_field_change_phrase(c)}" for c in changes
            )
            message = phrases
        else:
            message = f"{rt} content changed since last scan."
        out.append(_flag(
            rule_id="resource_updated",
            category="data_change",
            change_status="updated",
            message=message,
            source=item["key"],
        ))
    return out


def _resource_not_returned_flags(pdiff: dict) -> list[dict]:
    out: list[dict] = []
    for item in pdiff.get("not_returned", []):
        rt = item.get("resource_type", "resource")
        out.append(_flag(
            rule_id="resource_not_returned",
            category="data_availability",
            change_status="not_returned",
            message=(
                f"{rt} {item['key']} was present in the previous scan but is not "
                f"returned by the current API response (absence is not deletion)."
                if not item["key"].startswith(f"{rt}/")
                else (
                    f"{item['key']} was present in the previous scan but is not "
                    f"returned by the current API response (absence is not deletion)."
                )
            ),
            source=item["key"],
        ))
    return out


def _active_workflow_flags(current_resources: list[dict], patient_id: str) -> list[dict]:
    out: list[dict] = []
    for res in current_resources:
        if res.get("resourceType") not in _WORKFLOW_TYPES:
            continue
        if _patient_of(res) != patient_id:
            continue
        status = (res.get("status") or "").lower()
        if status not in _WORKFLOW_OPEN:
            continue
        rt = res.get("resourceType")
        label = (
            (res.get("code", {}) or {}).get("text")
            or res.get("description")
            or _ref(res)
        )
        out.append(_flag(
            rule_id="active_workflow_item",
            category="workflow",
            change_status=status,
            message=f"Open {rt} (status: {status}): {label}.",
            source=_ref(res),
        ))
    return out


def _patient_of(res: dict) -> str | None:
    """Best-effort patient id for a current resource (mirrors normalize.patient_ref)."""
    if res.get("resourceType") == "Patient":
        return res.get("id")
    for field in ("subject", "patient", "for", "beneficiary"):
        ref = res.get(field, {})
        if isinstance(ref, dict) and isinstance(ref.get("reference"), str):
            return ref["reference"].split("/")[-1]
    return None


def evaluate(pdiff: dict, current_resources: list[dict], patient_id: str) -> list[dict]:
    """Evaluate the §15 data/workflow rules for one patient.

    Args:
        pdiff: a patient-filtered diff
            ({new[], updated[], not_returned[], (unchanged[]), counts}) as produced
            by diff.filter_for_patient.
        current_resources: the latest-scan resources visible for this patient.
        patient_id: the patient whose board these flags feed.

    Returns:
        A list of flags, each exactly the shape documented in the module header.
        Pure: no I/O, no mutation of inputs.
    """
    flags: list[dict] = []
    flags += _new_resource_flags(pdiff)
    flags += _resource_updated_flags(pdiff)
    flags += _resource_not_returned_flags(pdiff)
    flags += _active_workflow_flags(current_resources, patient_id)
    return flags
