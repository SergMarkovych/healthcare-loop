# ADR-0003: Rules and form scope — data/workflow flags, not medical rules

- **Status:** Accepted
- **Proposed:** 2026-06-20 · **Accepted:** 2026-06-20
- **Deciders:** project lead, architect

## Context
The Patient Context Board and the Office Assistant both need to decide *what the tool is
allowed to assert*. A rules engine could (a) emit **care-gap / severity rules that score or
rank clinically** ("uncontrolled — order labs", "change med"), or (b) emit only
**source-backed data/workflow flags** (what changed since the last scan, what workflow items
are open). Similarly, the office side needs a lead form for the prefill moment — and the
question is whether to hardcode one form or build a generic registry. The hard product rule
is augment-not-replace: the AI restates source-backed facts only; the physician approves
every clinical output.

Alternatives: for rules — (a) clinical care-gap scoring vs (b) data/workflow flags only; for
forms — (c) one hardcoded form vs (d) a modular canonical-record → form registry.

## Decision
We **emit data/workflow flags only, never medical rules, and keep forms in a modular
registry**. The rules engine (`backend/fhir/rules.py`) produces structured flags
`{ruleId, category, changeStatus, message, source, clinicalInterpretation: null,
treatmentRecommendation: null}` (`rules.py:56-67`) — `new` / `updated` / `not_returned` /
`active_workflow` only. `clinicalInterpretation` is **structurally always null**, and a
forbidden-wording guard raises if interpretive text ever appears (`rules.py:41-53`). Form
prefill lives in `backend/office/forms.py` as a canonical record → form registry with
clinical fields explicitly flagged for physician judgement, so the lead form is a low-cost
swap, not a rebuild.

## Consequences
- **Positive:** auditable and safe — the tool flags *what changed* and *what is open*, never a
  clinical recommendation; the physician keeps all judgement. Adding/swapping a form costs
  minutes (registry-driven).
- **Negative:** the tool is deliberately "less smart" — clinical scoring and care-gap ranking
  stay a human task and are out of scope.
- **Trade-off accepted:** we forgo apparent clinical intelligence to stay firmly on the
  augment-not-replace side of the line.

## Compliance
**Fitness mechanism:** the interpretive-text guard (`rules.py:41-53`) and the structurally-null
clinical fields are covered by the green test suite; the modular form registry
(`backend/office/forms.py`) means adding/swapping a form must not require changes outside that
module. Source-backed: every flag and prefilled field carries a `source` / `.src` chip citing
the FHIR resource it restates.

## Notes
Author: project lead · Approvers: architect / review board · Last modified: 2026-06-20.
Supersedes: none. Superseded by: none. Source decision: `docs/design/DESIGN.md`
"Rules are data/workflow rules, not medical rules" decision block.
