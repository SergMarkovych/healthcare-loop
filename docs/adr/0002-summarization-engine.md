# ADR-0002: Summarization / extraction engine — deterministic builder + safety post-filter vs local model

- **Status:** Accepted
- **Proposed:** 2026-06-20 · **Accepted:** 2026-06-20
- **Deciders:** project lead, architect

## Context
The safe context summary and the form-field extraction can run two ways: through a **local
LLM (Ollama)**, or through a **deterministic** path that composes output from the structured
FHIR data alone. The most dangerous assumption is *"does a local model produce acceptable,
non-clinical output on real synthetic FHIR data?"* — answerable only by running it. Safety
(never emit diagnostic/prescriptive wording) and demo-reliability (never dead-end with no
model or network) are the driving characteristics. A cloud LLM was also on the table.

Alternatives: (a) local model only; (b) deterministic only; (c) deterministic by default with
an optional local model, governed by a safety filter; (d) cloud LLM.

## Decision
We **build prose deterministically by default and treat the local Ollama model as an optional
rephraser, with a forbidden-wording safety post-filter governing either path**
(`backend/fhir/summarize.py:22-27,111-153`). The model is engaged only when the deterministic
flags are unset; any model output containing clinical-decision wording is **discarded and the
deterministic text is used — fail safe, not fail open** (`summarize.py:146-153`). The
deterministic builder, which cannot invent clinical content, is always available and is the
container default. A cloud LLM is rejected outright (locality / data-sovereignty concern even
on synthetic data).

## Consequences
- **Positive:** the deterministic path guarantees a safe, stable, offline demo regardless of
  the model; the optional local model preserves the privacy/locality story when its quality
  holds; nothing patient-shaped leaves the machine.
- **Negative:** deterministic prose is plainer than a model's; model output varies run-to-run
  (mitigated by keeping it off by default).
- **Trade-off accepted:** we forgo always-on LLM polish for a bulletproof, locality-preserving
  default.

## Compliance
**Fitness function (automated):** the forbidden-wording filter rejects any clinical wording in
model output, covered by the green test suite alongside the `rules.py` interpretive-text guard
(`rules.py:41-53`, structurally `clinicalInterpretation: null`). **Toggles:**
`FORCE_DETERMINISTIC=1` (container default) forces the deterministic path; `FORCE_MOCK=1`
keeps the office extractor on the deterministic mock. Unset both + set `OLLAMA_HOST` /
`OLLAMA_MODEL` to enable the local model.

## Notes
Author: project lead · Approvers: architect / review board · Last modified: 2026-06-20.
Supersedes: none. Superseded by: none. Source decision: `docs/design/DESIGN.md`
"Deterministic builder + safety post-filter for AI summaries" decision block.
