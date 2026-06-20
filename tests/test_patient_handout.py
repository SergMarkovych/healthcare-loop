"""
Patient handout — deterministic readability grade + heuristic red-flag coverage.

The handout is built purely from an existing EncounterExtraction (no model call),
so these tests assert ordering/shape rather than exact float values, and exercise
the coverage heuristic directly with constructed extractions.
"""

from backend import mock
from backend.office.patient_handout import _flesch_kincaid_grade, build_handout
from backend.schema import (
    Confidence,
    EncounterExtraction,
    Problem,
    ProblemStatus,
)

def _problem(name: str, status: ProblemStatus) -> Problem:
    return Problem(name=name, status=status, evidence="snippet", confidence=Confidence.high)


def test_fk_grade_empty_is_zero():
    assert _flesch_kincaid_grade("") == 0.0
    assert _flesch_kincaid_grade("   ") == 0.0


def test_fk_grade_simple_below_clinical():
    simple = "The cat sat on the mat."
    clinical = (
        "Following your appointment, please continue the prescribed antihypertensive "
        "medication while monitoring for symptomatic deterioration, and return immediately "
        "should you experience cardiovascular or respiratory compromise."
    )
    assert _flesch_kincaid_grade(simple) < _flesch_kincaid_grade(clinical)


def test_build_handout_from_sample_one_extraction():
    extraction = mock.extract("", "sample-1")
    handout = build_handout(extraction)

    assert set(handout) == {
        "instructions", "safety_netting", "reading_grade",
        "readability_ok", "red_flag_coverage",
    }
    assert handout["instructions"]
    assert handout["safety_netting"]
    assert isinstance(handout["reading_grade"], float)
    assert set(handout["red_flag_coverage"]) == {
        "has_safety_netting", "active_problem_count", "covered", "uncovered_problems",
    }


def test_coverage_uncovered_when_netting_below_active_problems():
    extraction = EncounterExtraction(
        summary="x",
        problems=[
            _problem("Type 2 diabetes", ProblemStatus.worsening),
            _problem("Hypertension", ProblemStatus.ongoing),
            _problem("Asthma", ProblemStatus.new),
        ],
        safety_netting=["Seek urgent care for severe headache or chest pain."],
    )
    cov = build_handout(extraction)["red_flag_coverage"]

    assert cov["active_problem_count"] == 3
    assert cov["has_safety_netting"] is True
    assert cov["covered"] is False
    assert cov["uncovered_problems"]


def test_coverage_covered_when_netting_meets_active_problems():
    extraction = EncounterExtraction(
        summary="x",
        problems=[
            _problem("Type 2 diabetes", ProblemStatus.worsening),
            _problem("Resolved sinusitis", ProblemStatus.resolved),
        ],
        safety_netting=[
            "Return for chest pain or shortness of breath.",
            "Come back if blood pressure stays above 160/100.",
        ],
    )
    cov = build_handout(extraction)["red_flag_coverage"]

    assert cov["active_problem_count"] == 1
    assert cov["covered"] is True
    assert cov["uncovered_problems"] == []


def test_handout_endpoint(client):
    resp = client.get("/api/office/handout/req-2")
    assert resp.status_code == 200
    payload = resp.json()
    assert payload["status"] == "ok"

    handout = payload["handout"]
    assert set(handout) == {
        "instructions", "safety_netting", "reading_grade",
        "readability_ok", "red_flag_coverage",
    }
