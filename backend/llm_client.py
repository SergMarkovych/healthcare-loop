"""
LLM provider config + routing. Single source of truth for which model serves a
request and how it's called. Two providers:

  - ollama      (default) runs entirely on localhost; no patient text leaves the box.
  - openrouter  hosted; activated by LLM_PROVIDER=openrouter, needs OPENROUTER_API_KEY.

Callers go through `call_chat`. Provider-specific transport lives in the private
`_ollama_chat` / `_openrouter_chat` helpers. Config is exposed as module-level
constants so health/status endpoints can report the active provider.

Config via environment variables:
  LLM_PROVIDER        default ollama   ('openrouter' to use OpenRouter)
  OLLAMA_HOST         default http://localhost:11434
  OLLAMA_MODEL        default llama3.1
  OPENROUTER_API_KEY  default ""       (required when provider is openrouter)
  OPENROUTER_MODEL    default openai/gpt-4o-mini
"""

import os

LLM_PROVIDER = os.environ.get("LLM_PROVIDER", "ollama")
OLLAMA_HOST = os.environ.get("OLLAMA_HOST", "http://localhost:11434")
OLLAMA_MODEL = os.environ.get("OLLAMA_MODEL", "llama3.1")
OPENROUTER_API_KEY = os.environ.get("OPENROUTER_API_KEY", "")
OPENROUTER_MODEL = os.environ.get("OPENROUTER_MODEL", "openai/gpt-4o-mini")

OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"


def call_chat(messages: list[dict], json_schema: dict | None = None, timeout: int = 120) -> str:
    """Dispatch a chat completion to the active provider, returning the raw content string.

    json_schema is a Pydantic JSON schema dict for structured extraction, or None
    for freeform summarization.
    """
    if LLM_PROVIDER == "openrouter":
        return _openrouter_chat(messages, json_schema, timeout)
    return _ollama_chat(messages, json_schema, timeout)


def _ollama_chat(messages: list[dict], json_schema: dict | None, timeout: int) -> str:
    from ollama import Client

    client = Client(host=OLLAMA_HOST, timeout=timeout)
    kwargs: dict = {
        "model": OLLAMA_MODEL,
        "messages": messages,
        "options": {"temperature": 0},
    }
    if json_schema is not None:
        kwargs["format"] = json_schema
    resp = client.chat(**kwargs)
    return resp["message"]["content"]


def _openrouter_chat(messages: list[dict], json_schema: dict | None, timeout: int) -> str:
    import httpx

    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json",
        "HTTP-Referer": "https://github.com/SergMarkovych/healthcare-loop",
        "X-Title": "COMPASS HealthCare",
    }
    body: dict = {
        "model": OPENROUTER_MODEL,
        "messages": messages,
        "temperature": 0,
    }
    if json_schema is not None:
        body["response_format"] = {"type": "json_object"}

    with httpx.Client(timeout=timeout) as client:
        resp = client.post(OPENROUTER_URL, headers=headers, json=body)
        resp.raise_for_status()
        return resp.json()["choices"][0]["message"]["content"]
