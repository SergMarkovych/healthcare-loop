"""
Dictation summarizer (Work Stream 2, ADR-0005) — speech-text -> fixed OfficeSummary.

Deterministic, offline (FORCE_MOCK=1 via conftest). The summarizer restates and
structures the dictation; it must invent nothing. Cases cover form-hint detection,
action extraction, the never-invent invariant, and one endpoint round-trip.
"""

from backend.office import summarizer


def test_summarize_detects_referral_and_insurance_hints():
    text = ("Post-assessment for Ms. Lee. Send her to ENT for the hearing loss and "
            "fill out the insurance disability form for her time off work.")
    result = summarizer.summarize(text)

    assert "referral" in result.candidate_form_hints
    assert "insurance" in result.candidate_form_hints

    assert result.requested_actions, "expected concrete actions from the dictation"
    actions = " ".join(result.requested_actions).lower()
    assert "send her to ent" in actions
    assert "fill out the insurance disability form" in actions


def test_summarize_invents_nothing_for_sparse_dictation():
    text = "Patient seen today, doing well."
    result = summarizer.summarize(text)

    # No actions, no form intents, no fabricated patient context.
    assert result.requested_actions == []
    assert result.candidate_form_hints == []
    assert result.patient_context is None
    # The summary restates only what was said — no invented clinical content.
    assert result.summary == "Patient seen today, doing well"


def test_summarize_does_not_hallucinate_unmentioned_form_hints():
    # A referral is requested; no insurance/sick-note/school intent is present.
    text = "Refer the patient to cardiology for the palpitations."
    result = summarizer.summarize(text)

    assert result.candidate_form_hints == ["referral"]
    assert "insurance" not in result.candidate_form_hints
    assert "sick_note" not in result.candidate_form_hints


def test_summarize_endpoint_round_trip(client):
    text = "Send her to ENT and fill out the insurance disability form."
    resp = client.post("/api/office/summarize", json={"text": text})
    assert resp.status_code == 200
    payload = resp.json()

    assert "referral" in payload["candidate_form_hints"]
    assert "insurance" in payload["candidate_form_hints"]
    assert payload["requested_actions"]
    assert payload["patient_context"] is None
