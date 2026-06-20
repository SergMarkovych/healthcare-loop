"""LLM-path tests for the office summarizer (AB#664).

The deterministic path is covered in test_summarizer.py. These exercise the MODEL
branch (mirrors backend/llm.py) without a live model by patching
llm_client.call_chat and disabling FORCE_MOCK for the duration of each test.
"""
import json

from backend.office import summarizer


def _patch_llm(monkeypatch, responses):
    calls = {"n": 0}

    def fake_call_chat(messages, schema, timeout=120):
        r = responses[min(calls["n"], len(responses) - 1)]
        calls["n"] += 1
        if isinstance(r, Exception):
            raise r
        return r

    monkeypatch.setattr(summarizer, "FORCE_MOCK", False)
    monkeypatch.setattr(summarizer.llm_client, "call_chat", fake_call_chat)
    return calls


def test_llm_path_parses_valid_model_json(monkeypatch):
    payload = json.dumps({
        "summary": "Refer to ENT and complete insurance form.",
        "requested_actions": ["send her to ENT", "fill out the insurance form"],
        "candidate_form_hints": ["referral", "insurance"],
        "patient_context": "follow-up visit",
    })
    calls = _patch_llm(monkeypatch, [payload])
    out = summarizer.summarize("anything the physician dictated")
    assert calls["n"] == 1  # took the LLM path, not the mock
    assert out.summary == "Refer to ENT and complete insurance form."
    assert "referral" in out.candidate_form_hints
    assert "insurance" in out.candidate_form_hints
    assert out.patient_context == "follow-up visit"


def test_llm_path_retries_once_then_succeeds(monkeypatch):
    good = json.dumps({
        "summary": "ok", "requested_actions": [],
        "candidate_form_hints": [], "patient_context": None,
    })
    calls = _patch_llm(monkeypatch, ["not valid json", good])
    out = summarizer.summarize("text")
    assert calls["n"] == 2  # retried after the first invalid response
    assert out.summary == "ok"


def test_llm_path_degrades_to_mock_on_repeated_invalid(monkeypatch):
    calls = _patch_llm(monkeypatch, ["nope", "still bad"])
    out = summarizer.summarize("send her to ENT and fill out the insurance form")
    assert calls["n"] == 2  # tried twice, both invalid
    # fell back to the deterministic mock -> hints still detected from the text
    assert "referral" in out.candidate_form_hints
    assert "insurance" in out.candidate_form_hints


def test_llm_path_degrades_to_mock_on_exception(monkeypatch):
    calls = _patch_llm(monkeypatch, [ConnectionError("model down")])
    out = summarizer.summarize("order bloodwork for the patient")
    assert calls["n"] == 1  # raised on first call, no retry
    assert any("order" in a.lower() for a in out.requested_actions)
