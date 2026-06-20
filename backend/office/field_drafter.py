"""
AI-assisted draft generation for physician-flagged clinical form fields.

The office assistant flags genuine clinical-judgement fields (functional
limitations, prognosis, work/school capacity, onset, urgency) for the physician
rather than inventing them. When a model is available, this module pre-fills those
flagged fields with a *draft* — a clinically plausible starting point inferred from
the encounter's problems/medications, with a supporting evidence snippet and a
confidence flag. The physician verifies, edits, and signs everything; each draft is
gated behind an explicit physician confirmation in the UI before it counts as done.

Mirrors backend/llm.py's discipline: enforce the Pydantic JSON schema, temperature
0 (set in llm_client), validate + retry once on failure, and degrade to no drafts
on any error so the demo never dead-ends. Goes through llm_client.call_chat only.

Config via environment variables:
  FORCE_MOCK  set to 1 to skip the model entirely (no drafts)
"""

import json
import os

from backend import llm_client
from backend.schema import EncounterExtraction, FieldDraftSet

FORCE_MOCK = os.environ.get("FORCE_MOCK", "").lower() in ("1", "true", "yes")

SYSTEM_PROMPT = (
    "You draft administrative form fields from ONE primary-care encounter, as a STARTING "
    "POINT a physician verifies, edits, and signs — you are drafting, not deciding care. "
    "For each requested field, write a concise, clinically plausible draft based on the "
    "encounter's problems, medications, and their status. Put a short supporting snippet "
    "(a problem name, medication, or note phrase) in `evidence`, and set `confidence`: "
    "\"high\" if the field is directly stated, \"medium\" or \"low\" if you inferred it from "
    "the clinical picture. Do not fabricate specific numbers, dates, lab values, or test "
    "results that are not present. Only leave a value empty if the encounter gives nothing "
    "at all to base it on. Return ONLY JSON matching the schema."
)


def _messages(extraction: EncounterExtraction, field_specs: list[dict]) -> list[dict]:
    schema = json.dumps(FieldDraftSet.model_json_schema())
    fields = json.dumps(field_specs)
    extraction_json = json.dumps(extraction.model_dump())
    user = (
        "Draft the requested form fields from the encounter extraction below. "
        "Return JSON conforming to this schema:\n"
        f"{schema}\n\n"
        "--- REQUESTED FIELDS (field_id + label for context) ---\n"
        f"{fields}\n"
        "--- ENCOUNTER EXTRACTION (synthetic) ---\n"
        f"{extraction_json}\n"
        "--- END EXTRACTION ---"
    )
    return [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": user},
    ]


def draft_clinical_fields(extraction: EncounterExtraction, field_specs: list[dict]) -> dict[str, dict]:
    """Return {field_id: {value, evidence, confidence}} for fields the model supports.

    Fields the model can't ground in the extraction are absent; the caller leaves
    those blank. Returns {} when FORCE_MOCK is set or on any model/validation error —
    never raises.
    """
    if FORCE_MOCK or not field_specs:
        return {}

    try:
        messages = _messages(extraction, field_specs)
        schema = FieldDraftSet.model_json_schema()

        draft_set: FieldDraftSet | None = None
        for _ in range(2):
            content = llm_client.call_chat(messages, schema, timeout=120)
            try:
                draft_set = FieldDraftSet.model_validate_json(content)
                break
            except Exception as err:  # JSON or schema validation problem
                messages.append({"role": "assistant", "content": content})
                messages.append({
                    "role": "user",
                    "content": (
                        f"That response did not validate against the schema: {err}. "
                        "Return corrected JSON only, no commentary."
                    ),
                })
        if draft_set is None:
            return {}

        return {
            d.field_id: {"value": d.value, "evidence": d.evidence,
                         "confidence": d.confidence.value}
            for d in draft_set.drafts
            if d.value.strip()
        }

    except Exception as err:  # connection refused, model not pulled, timeout, etc.
        print(f"[field_drafter] model unavailable ({err}); no drafts.")
        return {}
