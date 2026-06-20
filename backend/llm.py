"""
Local LLM extraction via Ollama.

Key properties for the hackathon brief:
  - Runs entirely on localhost. No patient text leaves the machine.
  - Enforces the Pydantic JSON schema with Ollama's `format` parameter.
  - temperature=0 for stable schema adherence; validates + retries once on failure.
  - Falls back to the mock extractor if Ollama is unavailable, so the demo never
    dead-ends. The chosen mode ('local-model' | 'mock') is returned to the UI.

Config via environment variables:
  OLLAMA_HOST   default http://localhost:11434
  OLLAMA_MODEL  default llama3.1   (try qwen2.5, mistral, or gpt-oss too)
  FORCE_MOCK    set to 1 to skip the model entirely
"""

import json
import os

from backend import llm_client
from backend import mock
from backend.schema import (
    Confidence,
    EncounterExtraction,
    FollowUpTask,
    Investigation,
    MedAction,
    Medication,
    Owner,
    Problem,
    ProblemStatus,
    Urgency,
)

FORCE_MOCK = os.environ.get("FORCE_MOCK", "").lower() in ("1", "true", "yes")

# Aliases so callers (e.g. main.py health endpoint) keep reading these off llm.
OLLAMA_HOST = llm_client.OLLAMA_HOST
OLLAMA_MODEL = llm_client.OLLAMA_MODEL

SYSTEM_PROMPT = (
    "You are a clinical documentation assistant for a Canadian family medicine clinic. "
    "You read ONE primary-care encounter note and extract a structured, reviewable follow-up plan.\n"
    "Rules:\n"
    "- Extract only what the note supports. Never invent diagnoses, medications, doses, tests, or referrals.\n"
    "- If something is unclear or only implied, still include it but set its confidence to \"low\".\n"
    "- For every item, copy a short verbatim snippet from the note into the \"evidence\" field.\n"
    "- A clinician will review and edit everything you produce. You are drafting, not deciding care.\n"
    "Return ONLY a JSON object that matches the provided schema."
)


_EXAMPLE_NOTE = (
    "Family Medicine note. 58F with hypothyroidism, reports ongoing fatigue. "
    "Plan: increase levothyroxine to 75 mcg daily. Order TSH in 6 weeks. "
    "Advised to take levothyroxine on an empty stomach. "
    "Return in 3 months; sooner if palpitations or chest pain."
)

_EXAMPLE = EncounterExtraction(
    summary="Review of hypothyroidism with ongoing fatigue; levothyroxine dose increased.",
    problems=[
        Problem(
            name="Hypothyroidism",
            status=ProblemStatus.ongoing,
            evidence="hypothyroidism, reports ongoing fatigue",
            confidence=Confidence.high,
        )
    ],
    medications=[
        Medication(
            drug="Levothyroxine",
            action=MedAction.increased,
            detail="to 75 mcg daily",
            evidence="increase levothyroxine to 75 mcg daily",
            confidence=Confidence.high,
        )
    ],
    investigations=[
        Investigation(
            name="TSH",
            reason="Monitor thyroid replacement",
            urgency=Urgency.routine,
            evidence="Order TSH in 6 weeks",
            confidence=Confidence.high,
        )
    ],
    follow_up_tasks=[
        FollowUpTask(
            task="Recheck visit",
            owner=Owner.clinic,
            timeframe="3 months",
            priority=Urgency.routine,
            evidence="Return in 3 months",
            confidence=Confidence.high,
        )
    ],
    patient_instructions=["Take levothyroxine on an empty stomach."],
    safety_netting=["Return sooner than 3 months if you develop palpitations or chest pain."],
)

_EXAMPLE_JSON = _EXAMPLE.model_dump_json()


def _user_turn(note: str) -> str:
    schema = json.dumps(EncounterExtraction.model_json_schema())
    return (
        "Extract the structured follow-up plan from the encounter note below. "
        "Return JSON conforming to this schema:\n"
        f"{schema}\n\n"
        "--- ENCOUNTER NOTE (synthetic) ---\n"
        f"{note}\n"
        "--- END NOTE ---"
    )


def _messages(note: str) -> list[dict]:
    return [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": _user_turn(_EXAMPLE_NOTE)},
        {"role": "assistant", "content": _EXAMPLE_JSON},
        {"role": "user", "content": _user_turn(note)},
    ]


def extract(note: str, sample_id: str | None = None) -> tuple[EncounterExtraction, str]:
    """Return (extraction, mode). mode is 'local-model' or 'mock'."""
    if FORCE_MOCK:
        return mock.extract(note, sample_id), "mock"

    mode = "openrouter" if llm_client.LLM_PROVIDER == "openrouter" else "local-model"

    try:
        messages = _messages(note)
        schema = EncounterExtraction.model_json_schema()

        last_error: Exception | None = None
        for _ in range(2):
            content = llm_client.call_chat(messages, schema, timeout=120)
            try:
                return EncounterExtraction.model_validate_json(content), mode
            except Exception as err:  # JSON or schema validation problem
                last_error = err
                messages.append({"role": "assistant", "content": content})
                messages.append({
                    "role": "user",
                    "content": (
                        f"That response did not validate against the schema: {err}. "
                        "Return corrected JSON only, no commentary."
                    ),
                })
        # Model reachable but couldn't produce valid output — degrade gracefully.
        print(f"[llm] model output failed validation twice: {last_error}; using mock.")
        return mock.extract(note, sample_id), "mock"

    except Exception as err:  # connection refused, model not pulled, timeout, etc.
        print(f"[llm] local model unavailable ({err}); using mock.")
        return mock.extract(note, sample_id), "mock"
