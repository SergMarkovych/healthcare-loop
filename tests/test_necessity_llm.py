"""
LLM necessity gate for unknown request categories.

Known categories stay on the deterministic _RULES table (the model is never
reached). Unknown categories are classified by the model into one of the four
routes, conservatively defaulting to physician_review on low confidence or any
failure. conftest forces FORCE_MOCK=1 session-wide; tests that exercise the
model path monkeypatch necessity.FORCE_MOCK + necessity.llm_client.call_chat.
"""

from backend.office import necessity


def test_known_category_uses_rules_unchanged(monkeypatch):
    def _boom(*a, **kw):
        raise AssertionError("LLM must not be called for a known category")

    monkeypatch.setattr(necessity.llm_client, "call_chat", _boom)

    result = necessity.classify("sick_note")

    assert result == {
        "route": "eliminate", "who": "patient",
        "reason": necessity._RULES["sick_note"][2],
        "requires_physician": False,
    }


def test_unknown_category_force_mock_defaults_to_physician_review():
    result = necessity.classify("totally_new_category")

    assert result == {
        "route": "physician_review", "who": "physician",
        "reason": "Unrecognized request type — defaulting to physician review.",
        "requires_physician": True,
    }


def test_unknown_category_model_returns_delegate(monkeypatch):
    monkeypatch.setattr(necessity, "FORCE_MOCK", False)
    monkeypatch.setattr(necessity.llm_client, "call_chat",
                        lambda *a, **kw: '{"route":"delegate","who":"admin","reason":"x"}')

    result = necessity.classify("totally_new_category")

    assert result["route"] == "delegate"
    assert result["who"] == "admin"
    assert result["reason"] == "x"
    assert result["requires_physician"] is False


def test_unknown_category_invalid_route_clamped_to_physician_review(monkeypatch):
    monkeypatch.setattr(necessity, "FORCE_MOCK", False)
    monkeypatch.setattr(necessity.llm_client, "call_chat",
                        lambda *a, **kw: '{"route":"foo","who":"x","reason":"y"}')

    result = necessity.classify("totally_new_category")

    assert result["route"] == "physician_review"
    assert result["requires_physician"] is True


def test_unknown_category_model_raises_defaults_safely(monkeypatch):
    def _raise(*a, **kw):
        raise RuntimeError("connection refused")

    monkeypatch.setattr(necessity, "FORCE_MOCK", False)
    monkeypatch.setattr(necessity.llm_client, "call_chat", _raise)

    result = necessity.classify("totally_new_category")

    assert result == {
        "route": "physician_review", "who": "physician",
        "reason": "Unrecognized request type — defaulting to physician review.",
        "requires_physician": True,
    }
