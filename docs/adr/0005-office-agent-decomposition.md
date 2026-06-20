# ADR-0005: Decompose `/office` into narrow agents with deterministic-flow orchestration and a verification layer

- **Status:** Accepted
- **Proposed:** 2026-06-20 · **Accepted:** 2026-06-20
- **Deciders:** architect, project lead (direction captured from the COMPASS SME/expert panel)
- **Tracking:** AB#662 (Epic) · **Source:** `docs/original/ExpertSays/COMPASS_Session_Deliverables/`

> **Provenance.** The architectural direction was given by the COMPASS SME/expert panel.
> Architectural decisions require trade-off analysis in a specific business and technical
> context and are the architect's to ratify — this record adopts the panel's direction and
> documents the trade-offs that were weighed before acceptance.

## Context
The `/office` digital office assistant must turn a single physician voice capture into
multiple completed, validated forms — without fabricating clinical content. The SME panel
directed a "farm of narrow agents" over one monolithic assistant, on the explicit grounds
that broad context is what drives hallucination ("it has so many contexts that it forgets
half of them").

Alternatives considered:
- **(a) One general office-assistant agent.** Rejected: too much context per call; named by the
  SME as the hallucination source.
- **(b) Choreography between peer agents.** Rejected: Loop is a single-process modular monolith
  (one architecture quantum, see `ARCHITECTURE_DECOMPOSITION.md`); distributed/event-driven
  workflow adds coordination complexity without the microservices payoff and complicates error
  handling and state.
- **(c) An LLM orchestrator agent** deciding the workflow at runtime. Rejected: non-deterministic
  and demo-risky; conflicts with the demo-reliability requirement and the `FORCE_MOCK`
  deterministic posture.
- **(d) Deterministic-flow orchestration over narrow agents** *(chosen)*: a code-controlled
  mediator coordinates single-responsibility agents, with a machine verification stage before
  human validation.

## Decision
We decompose `/office` into single-responsibility units — a **summarizer/synthesizer**, a
**form layer**, and a **verifier/evaluator agent** — coordinated by a **deterministic
orchestration flow** that owns workflow state and the fan-out. The flow runs a **verification
stage** (completeness, grounding, "not invented" enforcement) and a **missing-information
prompt** before routing to the physician. A single **human-in-the-loop "approve all" gate** is
mandatory; `QuestionnaireResponse` is written **only after approval**.

We will **not** use an LLM orchestrator and will **not** use choreography.

**Form-layer reconciliation with ADR-0003 (decided by the architect, 2026-06-20).** The SME's
"one agent per form type" expresses the intent of *tight context per form* — not a mandate to
duplicate fill logic. ADR-0003 already delivers tight per-form context through the
**canonical-record + form registry** (`backend/office/forms.py`): each form sees only its
declared field list. We therefore **keep the canonical-record seam** and expose each form as a
**narrow logical contract** behind the shared template, rather than authoring N physical
form-filler modules. This honours both ADR-0005 (narrow scope as the anti-hallucination lever)
and ADR-0003 (no per-form duplication). The fitness functions below bind regardless of whether
an agent is physical or logical.

The lead-form priority (referral intelligence) is recorded separately in **ADR-0006**.

## Consequences
**Good.** Narrow scope reduces hallucination by design; the canonical record makes field-level
calibrated trust tractable; the deterministic flow is auditable and demo-safe; the verifier +
MD gate gives defense in depth (machine verifies, human validates); clean parallelization
across work streams.

**Costs / risks.** The orchestration flow becomes a coordination point — acceptable at
single-process scale, and a deliberate mediator avoids the accidental Front Controller
antipattern. The verifier adds one hop — trivial. The summarizer, promoted to its own module,
adds a seam to maintain — justified by its single fixed-format responsibility.

**Business justification.** *User satisfaction* (physician trust via fewer hallucinations →
adoption); *strategic positioning* (the verify-then-validate safety story differentiates with
the judging panel); *time to market* (modular seams keep the work streams parallel).

## Compliance (governance / fitness functions)
Enforced in automated tests (see AB#667):
1. No form field is emitted without an attached evidence reference **or** an explicit "not
   invented" flag.
2. The verifier stage must pass before any output reaches the MD review UI.
3. `QuestionnaireResponse` write-back is reachable **only** through the approval gate.
4. The orchestration flow contains **no model call that selects the next step**
   (deterministic-flow guard).

## Notes
Author: project lead, captured from the SME panel · Approvers: architect. **Extends** ADR-0002
(summarization engine) and ADR-0004 (build scope); **relates to** ADR-0003 (rules + form scope —
the form layer is reconciled above, not superseded); the lead-form decision is **ADR-0006**.
Supersedes: none. Revisit if a future scale requirement justifies splitting agents into
separate services, or if a form type's verification proves intractable as a single stage.
