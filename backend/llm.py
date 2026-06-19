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

from backend import mock
from backend.schema import EncounterExtraction

OLLAMA_HOST = os.environ.get("OLLAMA_HOST", "http://localhost:11434")
OLLAMA_MODEL = os.environ.get("OLLAMA_MODEL", "llama3.1")
FORCE_MOCK = os.environ.get("FORCE_MOCK", "").lower() in ("1", "true", "yes")

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


def _messages(note: str) -> list[dict]:
    schema = json.dumps(EncounterExtraction.model_json_schema())
    user = (
        "Extract the structured follow-up plan from the encounter note below. "
        "Return JSON conforming to this schema:\n"
        f"{schema}\n\n"
        "--- ENCOUNTER NOTE (synthetic) ---\n"
        f"{note}\n"
        "--- END NOTE ---"
    )
    return [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": user},
    ]


def extract(note: str, sample_id: str | None = None) -> tuple[EncounterExtraction, str]:
    """Return (extraction, mode). mode is 'local-model' or 'mock'."""
    if FORCE_MOCK:
        return mock.extract(note, sample_id), "mock"

    try:
        from ollama import Client
    except ImportError:
        return mock.extract(note, sample_id), "mock"

    try:
        client = Client(host=OLLAMA_HOST, timeout=120)
        messages = _messages(note)
        schema = EncounterExtraction.model_json_schema()

        last_error: Exception | None = None
        for _ in range(2):
            resp = client.chat(
                model=OLLAMA_MODEL,
                messages=messages,
                format=schema,
                options={"temperature": 0},
            )
            content = resp["message"]["content"]
            try:
                return EncounterExtraction.model_validate_json(content), "local-model"
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
