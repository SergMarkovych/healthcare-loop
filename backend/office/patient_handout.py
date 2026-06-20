"""
Patient handout view over an existing encounter extraction — no model call.

Surfaces the patient instructions and safety-netting already produced by
extraction as a clean handout, with two deterministic, offline checks:

  - a Flesch-Kincaid reading grade over the combined handout text, so the demo
    can flag instructions written above a plain-language target band, and
  - a red-flag coverage check: whether any safety-netting was produced and
    whether there is at least one safety-netting item per active problem.

The coverage check is a HEURISTIC. Safety-netting items are free text and are
NOT keyed to specific problems, so "covered" only means there are at least as
many safety-netting lines as active problems — it does not verify that each
active problem's red flags are actually addressed. `uncovered_problems` is a
best-effort positional guess, not a clinical claim.

This is a leaf module: it imports `schema` only, makes no model call, performs
no I/O, and `build_handout` never raises — so it stays robust offline.
"""

import re

from backend.schema import EncounterExtraction, ProblemStatus

_ACTIVE_STATUSES = {ProblemStatus.new, ProblemStatus.ongoing, ProblemStatus.worsening}

_VOWEL_GROUPS = re.compile(r"[aeiouy]+")
_WORD = re.compile(r"[A-Za-z]+(?:'[A-Za-z]+)?")
_SENTENCE = re.compile(r"[.!?]+")


def _count_syllables(word: str) -> int:
    groups = _VOWEL_GROUPS.findall(word.lower())
    return max(1, len(groups))


def _flesch_kincaid_grade(text: str) -> float:
    if not text or not text.strip():
        return 0.0
    words = _WORD.findall(text)
    if not words:
        return 0.0
    sentences = max(1, len([s for s in _SENTENCE.split(text) if s.strip()]))
    syllables = sum(_count_syllables(w) for w in words)
    return 0.39 * (len(words) / sentences) + 11.8 * (syllables / len(words)) - 15.59


def build_handout(extraction: EncounterExtraction) -> dict:
    instructions = list(extraction.patient_instructions)
    safety_netting = list(extraction.safety_netting)

    joined = " ".join(instructions + safety_netting)
    grade = round(_flesch_kincaid_grade(joined), 1)

    active = [p for p in extraction.problems if p.status in _ACTIVE_STATUSES]
    uncovered = [p.name for p in active[len(safety_netting):]]

    return {
        "instructions": instructions,
        "safety_netting": safety_netting,
        "reading_grade": grade,
        "readability_ok": grade <= 9.0,
        "red_flag_coverage": {
            "has_safety_netting": len(safety_netting) >= 1,
            "active_problem_count": len(active),
            "covered": len(safety_netting) >= 1 and len(safety_netting) >= len(active),
            "uncovered_problems": uncovered,
        },
    }
