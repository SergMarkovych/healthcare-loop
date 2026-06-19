"""
Offline fallback so the UI is demoable the moment you clone the repo.

`extract()` runs when no local model is reachable (Ollama not installed / not
running / model not pulled) or when FORCE_MOCK=1. It returns a real
EncounterExtraction so the human-in-the-loop review flow works end to end.

It is deliberately dumb: a canned high-quality extraction for sample-1, and a
light keyword heuristic for any other text. Swap in the real local model
(see llm.py) for actual extraction quality.
"""

import re

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
    Referral,
    Urgency,
)

_CANNED = {
    "sample-1": EncounterExtraction(
        summary="Routine review of suboptimally controlled type 2 diabetes and above-target hypertension.",
        problems=[
            Problem(name="Type 2 diabetes", status=ProblemStatus.worsening,
                    evidence="Type 2 diabetes, suboptimally controlled", confidence=Confidence.high),
            Problem(name="Hypertension", status=ProblemStatus.worsening,
                    evidence="Hypertension, above target", confidence=Confidence.high),
        ],
        medications=[
            Medication(drug="Metformin", action=MedAction.increased, detail="to 1000 mg twice daily",
                       evidence="Increase metformin to 1000 mg twice daily", confidence=Confidence.high),
            Medication(drug="Perindopril", action=MedAction.started, detail="4 mg daily",
                       evidence="Start perindopril 4 mg daily for blood pressure", confidence=Confidence.high),
        ],
        investigations=[
            Investigation(name="HbA1c", reason="Monitor glycaemic control", urgency=Urgency.routine,
                          evidence="Order HbA1c, lipid panel, creatinine/eGFR and urine ACR",
                          confidence=Confidence.high),
            Investigation(name="Lipid panel", reason="Cardiovascular risk", urgency=Urgency.routine,
                          evidence="lipid panel", confidence=Confidence.high),
            Investigation(name="Creatinine / eGFR", reason="Renal function before/after ACE inhibitor",
                          urgency=Urgency.routine, evidence="creatinine/eGFR", confidence=Confidence.high),
            Investigation(name="Urine ACR", reason="Diabetic nephropathy screen", urgency=Urgency.routine,
                          evidence="urine ACR", confidence=Confidence.high),
        ],
        referrals=[
            Referral(specialty="Diabetes education program", reason="Medication adherence support",
                     urgency=Urgency.routine,
                     evidence="Refer to diabetes education program for medication adherence support",
                     confidence=Confidence.high),
        ],
        follow_up_tasks=[
            FollowUpTask(task="Patient to monitor home BP twice weekly and bring the log",
                         owner=Owner.patient, timeframe="ongoing, before next visit",
                         priority=Urgency.routine,
                         evidence="monitor home BP twice weekly and bring the log next time",
                         confidence=Confidence.high),
            FollowUpTask(task="Recheck visit", owner=Owner.clinic, timeframe="3 months",
                         priority=Urgency.routine,
                         evidence="Recheck in 3 months", confidence=Confidence.high),
            FollowUpTask(task="Book overdue diabetic foot exam", owner=Owner.clinic,
                         timeframe="soon", priority=Urgency.soon,
                         evidence="diabetic foot exam is overdue and should be booked",
                         confidence=Confidence.medium),
        ],
        patient_instructions=[
            "Take metformin 1000 mg twice daily and the new blood pressure pill (perindopril) once daily.",
            "Check your blood pressure at home twice a week and write the numbers down.",
        ],
        safety_netting=[
            "Return to clinic or go to the ER for severe headache, chest pain, or shortness of breath.",
            "Come back sooner than 3 months if home blood pressure is consistently above 160/100.",
        ],
    ),
}


def _med_action(line: str) -> MedAction:
    l = line.lower()
    if "increase" in l or "titrate up" in l:
        return MedAction.increased
    if "decrease" in l or "reduce" in l or "lower" in l:
        return MedAction.decreased
    if "stop" in l or "discontinue" in l or "d/c" in l:
        return MedAction.stopped
    if "hold" in l:
        return MedAction.held
    if "continue" in l:
        return MedAction.continued
    return MedAction.started


def _heuristic(note: str) -> EncounterExtraction:
    """Very rough keyword pass — just enough to populate the review UI."""
    lines = [ln.strip(" -•\t") for ln in note.splitlines() if ln.strip(" -•\t")]
    first = next((ln for ln in lines if not ln.lower().startswith(("patient:", "family medicine"))), "")
    ex = EncounterExtraction(summary=(first[:160] or "Encounter (mock extraction)."))

    lab_terms = ["hba1c", "a1c", "cbc", "lipid", "tsh", "creatinine", "egfr", "acr",
                 "ferritin", "bloodwork", "ecg", "x-ray", "urinalysis", "panel"]
    med_verbs = ["start", "increase", "decrease", "reduce", "stop", "discontinue",
                 "hold", "continue", "titrate", "mg "]
    follow_terms = ["follow up", "follow-up", "f/u", "recheck", "reassess", "review in",
                    "return in", "book", "repeat", "reminder"]

    for ln in lines:
        low = ln.lower()
        if any(t in low for t in lab_terms) and "order" in low:
            for token in re.split(r",| and ", ln.split("Order", 1)[-1] if "Order" in ln else ln):
                token = token.strip(" .;")
                if token and any(t in token.lower() for t in lab_terms):
                    ex.investigations.append(Investigation(
                        name=token[:60], reason="", urgency=Urgency.routine,
                        evidence=ln[:120], confidence=Confidence.low))
        elif any(v in low for v in med_verbs) and "order" not in low:
            ex.medications.append(Medication(
                drug=ln[:60], action=_med_action(ln), detail="",
                evidence=ln[:120], confidence=Confidence.low))
        if "refer" in low:
            ex.referrals.append(Referral(
                specialty=ln[:60], reason="", urgency=Urgency.routine,
                evidence=ln[:120], confidence=Confidence.low))
        if any(t in low for t in follow_terms):
            ex.follow_up_tasks.append(FollowUpTask(
                task=ln[:80], owner=Owner.clinic, timeframe="see note",
                priority=Urgency.routine, evidence=ln[:120], confidence=Confidence.low))
        if "er" in low.split() or "emergency" in low or "return if" in low or "seek" in low:
            ex.safety_netting.append(ln[:160])
        if "advised" in low or "counsel" in low or "discussed" in low or "information on" in low:
            ex.patient_instructions.append(ln[:160])

    return ex


def extract(note: str, sample_id: str | None = None) -> EncounterExtraction:
    if sample_id and sample_id in _CANNED:
        return _CANNED[sample_id].model_copy(deep=True)
    return _heuristic(note)
