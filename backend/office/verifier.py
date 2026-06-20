"""
Verification gate for the digital medical office assistant (Work Stream 5, ADR-0005).

A pure, deterministic check on form-filler output. It answers one safety question:
does every value the assistant put on a form either trace to evidence or carry an
explicit not-invented flag, and are all required fields present?

Boundary (ADR-0005 fitness functions): this module reads form-filler output only.
It imports nothing from backend.fhir, calls no LLM, writes nothing, and selects no
workflow step. No randomness — same input, same VerifyResult.
"""

from pydantic import BaseModel

from backend.office.forms import FORMS


class VerifyField(BaseModel):
    name: str
    value: str | None
    required: bool
    evidence_ref: str | None
    not_invented_flag: bool


class VerifyRequest(BaseModel):
    form_type: str
    fields: list[VerifyField]


class VerifyResult(BaseModel):
    status: str  # "pass" | "flag"
    missing_required: list[str]
    ungrounded: list[str]
    notes: list[str]


def _is_empty(value: str | None) -> bool:
    return value is None or value.strip() == ""


def verify(req: VerifyRequest) -> VerifyResult:
    missing_required: list[str] = []
    ungrounded: list[str] = []
    notes: list[str] = []

    for field in req.fields:
        has_value = not _is_empty(field.value)

        if field.required and not has_value:
            missing_required.append(field.name)
            notes.append(f"{field.name}: required field is missing a value")

        if has_value and field.evidence_ref is None and not field.not_invented_flag:
            ungrounded.append(field.name)
            notes.append(
                f"{field.name}: value present without evidence or not-invented flag"
            )

    status = "flag" if (missing_required or ungrounded) else "pass"
    return VerifyResult(
        status=status,
        missing_required=missing_required,
        ungrounded=ungrounded,
        notes=notes,
    )


def from_form(form_type: str, form: dict) -> VerifyRequest:
    """Adapt the live forms.prefill_form output to the verify contract.

    `form` is the dict returned by forms.prefill_form: {form_id, title, fields: [...]}
    where each field carries id, value, evidence, needs_physician.
    """
    required_names = set(FORMS.get(form_type, {}).get("fields", []))
    fields: list[VerifyField] = []
    for cell in form.get("fields", []):
        name = cell["id"]
        raw_value = cell.get("value")
        value = None if _is_empty(raw_value) else raw_value
        evidence = cell.get("evidence")
        evidence_ref = None if _is_empty(evidence) else evidence
        fields.append(
            VerifyField(
                name=name,
                value=value,
                required=name in required_names,
                evidence_ref=evidence_ref,
                not_invented_flag=bool(cell.get("needs_physician", False)),
            )
        )
    return VerifyRequest(form_type=form_type, fields=fields)
