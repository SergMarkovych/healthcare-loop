"""
Dictation summarizer for the digital medical office assistant (Work Stream 2, ADR-0005).

A narrow agent with a FIXED output format: physician dictation (free speech text)
-> structured OfficeSummary. This is the entry point to the voice-capture fan-out
(AB#665): the summary it produces is what downstream form-suggestion consumes.

Boundary (ADR-0005 fitness functions): this module reads TEXT only. It imports
nothing from backend.fhir, writes nothing, and NEVER invents clinical content — it
restates and structures what the dictation actually says. The deterministic path is
fully offline and stable (same input, same OfficeSummary).

Mirrors backend/llm.py's discipline: a "never invent" system prompt, enforce the
Pydantic JSON schema, validate + retry once on failure, and degrade to the
deterministic mock on FORCE_MOCK or any model/validation error so the demo never
dead-ends. Goes through llm_client.call_chat only.

Config via environment variables:
  FORCE_MOCK  set to 1 to skip the model entirely (deterministic rule-based path)
"""

import json
import os
import re

from pydantic import BaseModel, Field

from backend import llm_client

FORCE_MOCK = os.environ.get("FORCE_MOCK", "").lower() in ("1", "true", "yes")

SYSTEM_PROMPT = (
    "You are a dictation summarizer for a Canadian family medicine clinic. You read ONE "
    "physician's post-assessment dictation and restate it as a structured summary that a "
    "clinician will review.\n"
    "Rules:\n"
    "- Restate and structure ONLY what the dictation says. Never invent diagnoses, "
    "medications, referrals, actions, or form intents that are not in the text.\n"
    "- `summary` is a single-line restatement of the dictation, no new content.\n"
    "- `requested_actions` are the concrete things the physician asked to be done, in the "
    "physician's own words.\n"
    "- `candidate_form_hints` are administrative form intents you can detect in the text "
    "(e.g. referral, insurance, sick_note, school_note, disability_tax_credit). Only "
    "include a hint the dictation actually supports.\n"
    "- `patient_context` is a short phrase of patient context if the dictation gives one, "
    "otherwise null.\n"
    "- A clinician reviews and edits everything. You are drafting, not deciding care.\n"
    "Return ONLY a JSON object that matches the provided schema."
)

# Form-intent vocabulary, aligned with backend/office/forms.py FORMS keys and the
# necessity gate categories: referral_ent -> "referral", insurance_std -> "insurance".
_FORM_HINT_KEYWORDS: dict[str, tuple[str, ...]] = {
    "referral": ("refer", "referral", "specialist", " ent", "cardiology",
                 "dermatology", "send her to", "send him to", "send them to"),
    "insurance": ("insurance", "insurer", "short-term disability", "std form",
                  "attending physician statement", "disability form"),
    "sick_note": ("sick note", "sick-note", "medical note for work", "time off work",
                  "off work", "doctor's note"),
    "school_note": ("school note", "school accommodation", "note for school",
                    "school form"),
    "disability_tax_credit": ("disability tax credit", "t2201", "dtc"),
}

# Verbs that open an imperative clinical instruction in dictation.
_ACTION_VERBS: tuple[str, ...] = (
    "send", "refer", "fill out", "fill in", "complete", "order", "book", "schedule",
    "arrange", "start", "increase", "decrease", "stop", "continue", "prescribe",
    "renew", "request", "follow up", "follow-up", "recheck", "repeat", "sign",
    "submit", "draft", "write",
)

_SENTENCE_SPLIT = re.compile(r"[.\n;]+| and (?=send|refer|fill|complete|order|book|"
                             r"schedule|arrange|start|stop|continue|prescribe|renew|"
                             r"request|sign|submit|draft|write|recheck|repeat)")


class OfficeSummary(BaseModel):
    summary: str = Field(
        description="One-line restatement of the dictation; no invented content",
    )
    requested_actions: list[str] = Field(
        default_factory=list,
        description="Concrete actions the physician asked to be done, in their words",
    )
    candidate_form_hints: list[str] = Field(
        default_factory=list,
        description="Administrative form intents detected in the dictation "
        "(e.g. referral, insurance, sick_note)",
    )
    patient_context: str | None = Field(
        default=None,
        description="Short patient-context phrase if the dictation states one, else null",
    )


def _detect_form_hints(text: str) -> list[str]:
    low = text.lower()
    hints: list[str] = []
    for hint, keywords in _FORM_HINT_KEYWORDS.items():
        if any(kw in low for kw in keywords):
            hints.append(hint)
    return hints


def _extract_actions(text: str) -> list[str]:
    actions: list[str] = []
    seen: set[str] = set()
    for raw in _SENTENCE_SPLIT.split(text):
        clause = raw.strip(" ,-•\t")
        if not clause:
            continue
        low = clause.lower()
        if any(re.search(rf"\b{re.escape(verb)}\b", low) for verb in _ACTION_VERBS):
            key = low
            if key not in seen:
                seen.add(key)
                actions.append(clause)
    return actions


def _mock_summarize(text: str) -> OfficeSummary:
    """Deterministic, offline rule-based summary. Restates only; invents nothing."""
    stripped = text.strip()
    first_sentence = next(
        (s.strip() for s in re.split(r"[.\n]+", stripped) if s.strip()), ""
    )
    summary = first_sentence[:200] if first_sentence else "Dictation (no content)."
    return OfficeSummary(
        summary=summary,
        requested_actions=_extract_actions(stripped),
        candidate_form_hints=_detect_form_hints(stripped),
        patient_context=None,
    )


def _messages(text: str) -> list[dict]:
    schema = json.dumps(OfficeSummary.model_json_schema())
    user = (
        "Summarize the physician dictation below into the fixed structured format. "
        "Restate only — invent nothing. Return JSON conforming to this schema:\n"
        f"{schema}\n\n"
        "--- DICTATION ---\n"
        f"{text}\n"
        "--- END DICTATION ---"
    )
    return [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": user},
    ]


def summarize(text: str) -> OfficeSummary:
    """Structure physician dictation into an OfficeSummary.

    Deterministic rule-based path when FORCE_MOCK is set or the model is unavailable;
    otherwise an LLM path mirroring llm.py (schema-validated, retry-once, never-invent).
    Never raises — degrades to the deterministic path on any error.
    """
    if FORCE_MOCK:
        return _mock_summarize(text)

    try:
        messages = _messages(text)
        schema = OfficeSummary.model_json_schema()

        for _ in range(2):
            content = llm_client.call_chat(messages, schema, timeout=120)
            try:
                return OfficeSummary.model_validate_json(content)
            except Exception as err:  # JSON or schema validation problem
                messages.append({"role": "assistant", "content": content})
                messages.append({
                    "role": "user",
                    "content": (
                        f"That response did not validate against the schema: {err}. "
                        "Return corrected JSON only, no commentary."
                    ),
                })
        print("[summarizer] model output failed validation twice; using mock.")
        return _mock_summarize(text)

    except Exception as err:  # connection refused, model not pulled, timeout, etc.
        print(f"[summarizer] model unavailable ({err}); using mock.")
        return _mock_summarize(text)
