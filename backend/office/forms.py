"""
Forms layer for the "digital medical office assistant" (challenge area #5).

The idea the clinicians and AI experts both ranked highest: auto-populate common
paperwork (insurance forms, disability applications, school notes) from existing
chart data, with structured, auditable, physician-reviewable output.

Design honesty (calibrated trust, per the Developer Guide):
  - Administrative / known fields (name, DOB, diagnosis, current meds) are
    auto-filled from the chart, each with an evidence snippet + confidence.
  - Genuine clinical-judgement fields (functional limitations, prognosis, work
    capacity) are NOT invented. They are flagged for the physician to complete.
  - One canonical FunctionalLimitations record feeds every form — write the
    facts once, reuse across forms.
"""

from backend.schema import EncounterExtraction

# Each canonical field carries value + provenance so the UI can show calibrated trust.
# role: "auto" (chart-derived) | "physician" (clinical judgement, must be completed by MD)
CANONICAL_FIELDS = [
    "patient_name", "date_of_birth", "diagnosis", "current_medications",
    "onset_date", "functional_limitations", "expected_duration",
    "prognosis", "work_capacity", "school_capacity",
]


def _field(value="", role="auto", confidence="medium", evidence="", needs_physician=False):
    return {"value": value, "role": role, "confidence": confidence,
            "evidence": evidence, "needs_physician": needs_physician}


def build_functional_limitations(extraction: EncounterExtraction, patient_context: dict | None) -> dict:
    """Derive the canonical record from an encounter extraction + optional FHIR context."""
    pc = patient_context or {}
    fl: dict[str, dict] = {}

    fl["patient_name"] = _field(pc.get("name", ""), "auto", "high",
                                "Patient resource (FHIR)" if pc.get("name") else "", False)
    fl["date_of_birth"] = _field(pc.get("birthDate", ""), "auto", "high",
                                 "Patient resource (FHIR)" if pc.get("birthDate") else "", False)

    if extraction.problems:
        p = extraction.problems[0]
        fl["diagnosis"] = _field(p.name, "auto", p.confidence.value, p.evidence, False)
    else:
        fl["diagnosis"] = _field("", "auto", "low", "", False)

    if extraction.medications:
        meds = "; ".join(f"{m.drug} ({m.action.value}{', ' + m.detail if m.detail else ''})"
                         for m in extraction.medications)
        ev = extraction.medications[0].evidence
        fl["current_medications"] = _field(meds, "auto", "medium", ev, False)
    else:
        fl["current_medications"] = _field("", "auto", "low", "", False)

    # Expected duration can sometimes be inferred from a follow-up timeframe.
    dur = next((t.timeframe for t in extraction.follow_up_tasks if t.timeframe), "")
    fl["expected_duration"] = _field(dur, "physician" if not dur else "auto",
                                     "low", "", needs_physician=not dur)

    # Genuine clinical-judgement fields — never invented.
    fl["onset_date"] = _field("", "physician", "low",
                              "Not reliably in the note — confirm from chart", True)
    fl["functional_limitations"] = _field("", "physician", "low",
                                          "Requires your clinical judgement", True)
    fl["prognosis"] = _field("", "physician", "low", "Requires your clinical judgement", True)
    fl["work_capacity"] = _field("", "physician", "low", "Requires your clinical judgement", True)
    fl["school_capacity"] = _field("", "physician", "low", "Requires your clinical judgement", True)
    return fl


# Form registry: which canonical fields each form needs, in order.
FORMS = {
    "disability_tax_credit": {
        "title": "Disability Tax Credit (T2201) — medical certification",
        "fields": ["patient_name", "date_of_birth", "diagnosis", "onset_date",
                   "functional_limitations", "expected_duration", "prognosis"],
    },
    "insurance_std": {
        "title": "Insurer short-term disability — attending physician statement",
        "fields": ["patient_name", "date_of_birth", "diagnosis", "current_medications",
                   "functional_limitations", "work_capacity", "expected_duration", "prognosis"],
    },
    "school_note": {
        "title": "School accommodation note",
        "fields": ["patient_name", "date_of_birth", "diagnosis",
                   "school_capacity", "expected_duration"],
    },
}

FIELD_LABELS = {
    "patient_name": "Patient name", "date_of_birth": "Date of birth",
    "diagnosis": "Diagnosis", "current_medications": "Current medications",
    "onset_date": "Date of onset", "functional_limitations": "Functional limitations",
    "expected_duration": "Expected duration", "prognosis": "Prognosis",
    "work_capacity": "Work capacity / restrictions", "school_capacity": "School capacity / restrictions",
}


def prefill_form(form_id: str, fl: dict) -> dict:
    """Project the canonical record onto a specific form's fields."""
    spec = FORMS[form_id]
    fields = []
    for key in spec["fields"]:
        cell = fl.get(key, _field())
        fields.append({
            "id": key, "label": FIELD_LABELS.get(key, key),
            "value": cell["value"], "role": cell["role"],
            "confidence": cell["confidence"], "evidence": cell["evidence"],
            "needs_physician": cell["needs_physician"],
        })
    auto = sum(1 for f in fields if f["role"] == "auto")
    return {"form_id": form_id, "title": spec["title"], "fields": fields,
            "auto_filled": auto, "physician_fields": len(fields) - auto}
