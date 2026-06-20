"""
Referral intelligence — free-text reason -> specialty mapping.

When a local model is available, the reason is mapped to specialties by the LLM
(restricted to the fixed directory). When no model is available (FORCE_MOCK), the
deterministic keyword matcher is used instead. Either way the directory,
scope-matching, rejection-risk, and ranking stay deterministic — the model never
invents specialties or sets a rejection-risk score.
"""

from backend.office import referral_intel


def _by_name(rows: list[dict]) -> dict[str, dict]:
    return {r["specialist_name"]: r for r in rows}


def test_suggest_force_mock_uses_keyword_matcher():
    rows = referral_intel.suggest("pediatric ENT hearing loss")

    assert rows, "keyword matcher should return ENT specialists"
    assert all(r["specialty"] == "ENT" for r in rows)
    assert "Dr. Priya Anand" in _by_name(rows)


def test_suggest_llm_path_keeps_rejection_risk_deterministic(monkeypatch):
    monkeypatch.setattr(referral_intel, "FORCE_MOCK", False)
    monkeypatch.setattr(referral_intel.llm_client, "call_chat",
                        lambda *a, **kw: '{"specialties":["ENT"]}')

    rows = referral_intel.suggest("8yo failed a school hearing screen")

    assert rows, "LLM-mapped ENT should yield ENT specialists"
    assert all(r["specialty"] == "ENT" for r in rows)
    assert _by_name(rows)["Dr. Marcus Webb"]["rejection_risk"] == "high"


def test_suggest_filters_hallucinated_specialty(monkeypatch):
    monkeypatch.setattr(referral_intel, "FORCE_MOCK", False)
    monkeypatch.setattr(referral_intel.llm_client, "call_chat",
                        lambda *a, **kw: '{"specialties":["Dermatology"]}')

    rows = referral_intel.suggest("a curious rash with no other clues")

    assert all(r["specialty"] in referral_intel._DIRECTORY for r in rows)
    assert "Dermatology" not in {r["specialty"] for r in rows}


def test_suggest_never_raises_falls_back_to_keyword(monkeypatch):
    def _boom(*a, **kw):
        raise RuntimeError("model down")

    monkeypatch.setattr(referral_intel, "FORCE_MOCK", False)
    monkeypatch.setattr(referral_intel.llm_client, "call_chat", _boom)

    rows = referral_intel.suggest("pediatric ENT hearing loss")

    assert isinstance(rows, list)
    assert all(r["specialty"] == "ENT" for r in rows)
