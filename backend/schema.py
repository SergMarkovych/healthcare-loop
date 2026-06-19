"""
Structured output schema for the encounter -> follow-up extraction.

This is the contract the local LLM must fill. Every clinical item carries:
  - the extracted fields,
  - an `evidence` snippet copied from the note (so a clinician can verify it),
  - a `confidence` flag (low-confidence items get surfaced for review in the UI).

The schema is intentionally one level deep (arrays of flat objects) so that
small local models can follow it reliably. If a particular model struggles
with the enum constraints, relax the Enum fields to plain `str` (see README).
"""

from enum import Enum

from pydantic import BaseModel, Field


class Confidence(str, Enum):
    high = "high"
    medium = "medium"
    low = "low"


class ProblemStatus(str, Enum):
    new = "new"
    ongoing = "ongoing"
    resolved = "resolved"
    worsening = "worsening"
    improving = "improving"


class MedAction(str, Enum):
    started = "started"
    stopped = "stopped"
    increased = "increased"
    decreased = "decreased"
    continued = "continued"
    held = "held"


class Urgency(str, Enum):
    routine = "routine"
    soon = "soon"
    urgent = "urgent"


class Owner(str, Enum):
    patient = "patient"
    clinic = "clinic"
    physician = "physician"


class Problem(BaseModel):
    name: str = Field(description="Problem or diagnosis addressed at this visit")
    status: ProblemStatus
    evidence: str = Field(description="Short snippet copied verbatim from the note")
    confidence: Confidence


class Medication(BaseModel):
    drug: str
    action: MedAction
    detail: str = Field(default="", description="Dose / frequency / instructions, if stated")
    evidence: str
    confidence: Confidence


class Investigation(BaseModel):
    name: str = Field(description="Test, lab, or imaging ordered")
    reason: str = Field(default="")
    urgency: Urgency = Urgency.routine
    evidence: str
    confidence: Confidence


class Referral(BaseModel):
    specialty: str
    reason: str = Field(default="")
    urgency: Urgency = Urgency.routine
    evidence: str
    confidence: Confidence


class FollowUpTask(BaseModel):
    task: str = Field(description="A concrete action to close the loop on")
    owner: Owner = Field(description="Who is responsible: patient, clinic, or physician")
    timeframe: str = Field(description="When it should happen, e.g. '2 weeks', 'before next visit'")
    priority: Urgency = Urgency.routine
    evidence: str
    confidence: Confidence


class EncounterExtraction(BaseModel):
    summary: str = Field(description="One-line clinical summary of the encounter")
    problems: list[Problem] = Field(default_factory=list)
    medications: list[Medication] = Field(default_factory=list)
    investigations: list[Investigation] = Field(default_factory=list)
    referrals: list[Referral] = Field(default_factory=list)
    follow_up_tasks: list[FollowUpTask] = Field(default_factory=list)
    patient_instructions: list[str] = Field(
        default_factory=list,
        description="Plain-language instructions for the patient",
    )
    safety_netting: list[str] = Field(
        default_factory=list,
        description="Red-flag symptoms / when to seek urgent care",
    )
