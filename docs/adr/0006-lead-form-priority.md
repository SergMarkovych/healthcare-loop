# ADR-0006: Lead form priority for `/office` — referral intelligence, carried by form auto-fill

- **Status:** Accepted (pending SME confirmation of local form frequency)
- **Proposed:** 2026-06-20 · **Accepted:** 2026-06-20
- **Deciders:** architect, project lead (foresight brief from the COMPASS session)
- **Tracking:** AB#662 (Epic) · **Source:** `docs/original/ExpertSays/COMPASS_Session_Deliverables/FORM_PRIORITIZATION_DECISION.md`

## Context
ADR-0003 kept the form layer a modular registry and explicitly left the *lead* form — the one
that anchors the demo and the pitch — as "a low-cost swap." This record resolves that open
decision. The choice is constrained by what we can demo reliably on **FHIR Tier 1/2** data
(Patient, Condition, MedicationRequest, Observation, Encounter; Immunization, AllergyIntolerance,
DiagnosticReport) and by the competitive landscape the physician panel surfaced: an AI scribe and
an AI inbox/fax manager are **already on physicians' desks**.

Seven candidate lead forms were scored on clinical importance, technical feasibility on our
stack, safety/privacy, workflow fit, competitive differentiation, live-demo reliability, and
calibrated-trust showcase. Referral intelligence (A) and form auto-fill (B) tied highest;
inbox/fax triage (F) was killed on differentiation (head-on with the deployed inbox manager);
billing reconciliation (G) was killed on feasibility (lives outside Tier 1/2).

## Decision
The `/office` **lead is referral-package generation with specialist/form/portal matching** (A),
demoed on Tier 1/2 reads with `QuestionnaireResponse` write-back. **Disability/insurance form
auto-fill** (B) is the co-primary, carrying the calibrated-trust demonstration. The **necessity
gate** (sick note → attestation, C) frames the demo opener. **Inbox/fax triage** is excluded
from the lead (competitive overlap) and **billing reconciliation** is roadmap. **Referral
auto-resubmission** is explicitly v2 (requires Tier 3 state — Task/ServiceRequest, rarely present
in demo data).

A leads over B because differentiation is the scarcest asset in a room that already has scribes
and an inbox manager: referral intelligence is the one workflow no competitor on the desk solves.
B is the safer, fabrication-proof piece, so it *carries* the trust moment rather than leading.
Referral intelligence is already implemented (`backend/office/referral_intel.py`, AB#650).

## Consequences
- **Positive:** leads on the unclaimed wedge; the trust moment runs on the most demo-safe path;
  the necessity-gate opener establishes Loop's signature ("we keep it off your desk").
- **Negative / dependency:** the demo depends on a curated specialist directory, acknowledged as
  a real integration surface, not a solved problem. The live demo runs in the deterministic path
  (`FORCE_MOCK=1`) to guarantee no fabricated fields in front of evidence judges.
- **Trade-off accepted:** we forgo the broadest coverage (inbox/billing) for a sharply
  differentiated, demo-safe lead.

## Compliance
The fan-out (ADR-0005) showcases exactly this prioritized set as its candidate forms. Every
prefilled field carries a `source`/evidence chip or a "not invented" flag (ADR-0005 fitness
function 1). No Tier 3 read is required for the lead path.

## Notes
Author: project lead · Approvers: architect. Relates to ADR-0003 (form scope) and ADR-0005
(decomposition — embeds this set as the fan-out's showcased forms). Supersedes: none.
**Trigger to revisit:** the SME panel names a different dominant local form (then re-aim B at
that exact form — same canonical-record machinery), or the specialist-directory mock fails the
pre-demo dry run (then B leads and A demotes to a supporting line).
