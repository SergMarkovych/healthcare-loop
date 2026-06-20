"""
Provider routing — backend.llm_client.

Verifies:
  - call_chat routes to Ollama or OpenRouter based on LLM_PROVIDER
  - json_schema forwarded correctly by each provider
  - extract() returns the right mode string per provider
  - summarize() returns the right mode string per provider
"""

from unittest.mock import MagicMock, patch

import pytest

from backend import llm_client


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_openrouter_mock(content: str = "response"):
    mock_resp = MagicMock()
    mock_resp.json.return_value = {"choices": [{"message": {"content": content}}]}
    mock_resp.raise_for_status = MagicMock()

    mock_http = MagicMock()
    mock_http.__enter__ = MagicMock(return_value=mock_http)
    mock_http.__exit__ = MagicMock(return_value=False)
    mock_http.post.return_value = mock_resp
    return mock_http


# ---------------------------------------------------------------------------
# Routing
# ---------------------------------------------------------------------------

def test_call_chat_routes_to_openrouter(monkeypatch):
    monkeypatch.setattr(llm_client, "LLM_PROVIDER", "openrouter")
    monkeypatch.setattr(llm_client, "OPENROUTER_API_KEY", "test-key")

    mock_http = _make_openrouter_mock("hello")
    with patch("httpx.Client", return_value=mock_http):
        result = llm_client.call_chat([{"role": "user", "content": "test"}])

    assert result == "hello"
    mock_http.post.assert_called_once()


def test_call_chat_routes_to_ollama(monkeypatch):
    monkeypatch.setattr(llm_client, "LLM_PROVIDER", "ollama")

    mock_ollama = MagicMock()
    mock_ollama.chat.return_value = {"message": {"content": "ollama-response"}}

    with patch("ollama.Client", return_value=mock_ollama):
        result = llm_client.call_chat([{"role": "user", "content": "test"}])

    assert result == "ollama-response"


# ---------------------------------------------------------------------------
# Schema forwarding
# ---------------------------------------------------------------------------

def test_openrouter_adds_json_object_format_when_schema_given(monkeypatch):
    monkeypatch.setattr(llm_client, "LLM_PROVIDER", "openrouter")
    monkeypatch.setattr(llm_client, "OPENROUTER_API_KEY", "test-key")

    mock_http = _make_openrouter_mock("{}")
    schema = {"type": "object", "properties": {"name": {"type": "string"}}}

    with patch("httpx.Client", return_value=mock_http):
        llm_client.call_chat([{"role": "user", "content": "x"}], json_schema=schema)

    body = mock_http.post.call_args[1]["json"]
    assert body.get("response_format") == {"type": "json_object"}


def test_openrouter_omits_format_when_no_schema(monkeypatch):
    monkeypatch.setattr(llm_client, "LLM_PROVIDER", "openrouter")
    monkeypatch.setattr(llm_client, "OPENROUTER_API_KEY", "test-key")

    mock_http = _make_openrouter_mock("text")

    with patch("httpx.Client", return_value=mock_http):
        llm_client.call_chat([{"role": "user", "content": "x"}], json_schema=None)

    body = mock_http.post.call_args[1]["json"]
    assert "response_format" not in body


def test_ollama_forwards_format_param_when_schema_given(monkeypatch):
    monkeypatch.setattr(llm_client, "LLM_PROVIDER", "ollama")

    mock_ollama = MagicMock()
    mock_ollama.chat.return_value = {"message": {"content": "ok"}}
    schema = {"type": "object"}

    with patch("ollama.Client", return_value=mock_ollama):
        llm_client.call_chat([{"role": "user", "content": "x"}], json_schema=schema)

    kwargs = mock_ollama.chat.call_args[1]
    assert kwargs.get("format") == schema


def test_ollama_omits_format_when_no_schema(monkeypatch):
    monkeypatch.setattr(llm_client, "LLM_PROVIDER", "ollama")

    mock_ollama = MagicMock()
    mock_ollama.chat.return_value = {"message": {"content": "ok"}}

    with patch("ollama.Client", return_value=mock_ollama):
        llm_client.call_chat([{"role": "user", "content": "x"}], json_schema=None)

    kwargs = mock_ollama.chat.call_args[1]
    assert "format" not in kwargs


# ---------------------------------------------------------------------------
# extract() mode string
# ---------------------------------------------------------------------------

def test_extract_returns_openrouter_mode(monkeypatch):
    from backend import llm
    from backend import mock as backend_mock

    monkeypatch.setattr(llm, "FORCE_MOCK", False)
    monkeypatch.setattr(llm_client, "LLM_PROVIDER", "openrouter")

    valid_json = backend_mock.extract("note", None).model_dump_json()
    monkeypatch.setattr(llm_client, "call_chat", lambda *a, **kw: valid_json)

    _, mode = llm.extract("a note")
    assert mode == "openrouter"


def test_extract_returns_local_model_mode(monkeypatch):
    from backend import llm
    from backend import mock as backend_mock

    monkeypatch.setattr(llm, "FORCE_MOCK", False)
    monkeypatch.setattr(llm_client, "LLM_PROVIDER", "ollama")

    valid_json = backend_mock.extract("note", None).model_dump_json()
    monkeypatch.setattr(llm_client, "call_chat", lambda *a, **kw: valid_json)

    _, mode = llm.extract("a note")
    assert mode == "local-model"


def test_extract_falls_back_to_mock_on_provider_error(monkeypatch):
    from backend import llm

    monkeypatch.setattr(llm, "FORCE_MOCK", False)
    monkeypatch.setattr(llm_client, "LLM_PROVIDER", "openrouter")
    monkeypatch.setattr(llm_client, "call_chat",
                        MagicMock(side_effect=Exception("connection refused")))

    _, mode = llm.extract("a note")
    assert mode == "mock"


# ---------------------------------------------------------------------------
# summarize() mode string
# ---------------------------------------------------------------------------

def _board_args():
    patient_resource = {
        "name": [{"given": ["Alice"], "family": "Test"}],
        "gender": "female",
        "birthDate": "1980-01-01",
    }
    pdiff = {
        "new": [], "updated": [], "not_returned": [],
        "counts": {"new": 0, "updated": 0, "not_returned": 0},
    }
    return "p1", patient_resource, pdiff, [], []


def test_summarize_returns_openrouter_mode(monkeypatch):
    from backend.fhir import summarize

    monkeypatch.setattr(summarize, "FORCE_DETERMINISTIC", False)
    monkeypatch.setattr(llm_client, "LLM_PROVIDER", "openrouter")
    monkeypatch.setattr(llm_client, "call_chat",
                        lambda *a, **kw: "Patient context assembled from the FHIR API.")

    _, mode = summarize.summarize(*_board_args())
    assert mode == "openrouter"


def test_summarize_returns_local_model_mode(monkeypatch):
    from backend.fhir import summarize

    monkeypatch.setattr(summarize, "FORCE_DETERMINISTIC", False)
    monkeypatch.setattr(llm_client, "LLM_PROVIDER", "ollama")
    monkeypatch.setattr(llm_client, "call_chat",
                        lambda *a, **kw: "Patient context assembled from the FHIR API.")

    _, mode = summarize.summarize(*_board_args())
    assert mode == "local-model"


def test_summarize_falls_back_to_deterministic_on_provider_error(monkeypatch):
    from backend.fhir import summarize

    monkeypatch.setattr(summarize, "FORCE_DETERMINISTIC", False)
    monkeypatch.setattr(llm_client, "LLM_PROVIDER", "openrouter")
    monkeypatch.setattr(llm_client, "call_chat",
                        MagicMock(side_effect=Exception("network error")))

    _, mode = summarize.summarize(*_board_args())
    assert mode == "deterministic"
