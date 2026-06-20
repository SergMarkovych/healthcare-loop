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


# --- ranking, hint, and edge-case contract (keyword path via conftest FORCE_MOCK) ---

def test_ranking_accepts_first_then_by_rejection_risk():
    rows = referral_intel.suggest("pediatric ENT hearing loss evaluation")
    assert len(rows) == 3
    # accept-scope rows sort ahead of non-accept rows
    accept_flags = [r["accepts_scope"] for r in rows]
    assert accept_flags == sorted(accept_flags, key=lambda a: not a)
    # the accepting low-risk specialist is on top; the adult-only high-risk one is last
    assert rows[0]["specialist_name"] == "Dr. Priya Anand"
    assert rows[0]["accepts_scope"] is True and rows[0]["rejection_risk"] == "low"
    assert rows[-1]["specialist_name"] == "Dr. Marcus Webb"
    assert rows[-1]["accepts_scope"] is False and rows[-1]["rejection_risk"] == "high"


def test_specialty_hint_is_case_insensitive():
    rows = referral_intel.suggest("anything", specialty_hint="ent")
    assert rows and all(r["specialty"] == "ENT" for r in rows)


def test_specialty_hint_selects_that_directory():
    rows = referral_intel.suggest("palpitations", specialty_hint="Cardiology")
    assert rows and {r["specialty"] for r in rows} == {"Cardiology"}


def test_no_matching_specialty_returns_empty():
    assert referral_intel.suggest("a dermatology rash on the arm") == []


def test_empty_reason_returns_empty():
    assert referral_intel.suggest("") == []


def test_every_row_carries_the_full_contract():
    keys = {"specialist_name", "clinic", "phone", "specialty",
            "accepts_scope", "rejection_risk", "notes"}
    for r in referral_intel.suggest("diabetes thyroid", specialty_hint="Endocrinology"):
        assert keys <= set(r)
        assert r["rejection_risk"] in {"low", "medium", "high"}


def test_suggest_never_raises_on_bad_input():
    assert referral_intel.suggest(None) == []
    assert referral_intel.suggest(123) == []  # type: ignore[arg-type]
