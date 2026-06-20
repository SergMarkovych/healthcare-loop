# ADR-0004: Build scope — lean MVP on one shared substrate vs a production stack

- **Status:** Accepted
- **Proposed:** 2026-06-20 · **Accepted:** 2026-06-20
- **Deciders:** project lead, architect

## Context
The brief rewards a focused, actionable, measurable prototype on a tight build budget. Two
questions had to be settled together: (1) **the stack** — the canonical V4 "production story"
is .NET 8 + PostgreSQL + React with RBAC/audit/encryption, while a Python reference build
("Loop") already runs offline end-to-end; and (2) **scope** — whether to build the full set of
production controls now, or match build depth to a kill-gated demo. A third question — build
one product direction or two — was answered by the shared FHIR substrate making both cheap.

Alternatives: for stack — (a) .NET 8 + PostgreSQL + React vs (b) Python + Streamlit vs
(c) Python + FastAPI + SQLite + vanilla-JS; for scope — (d) production controls now vs
(e) lean MVP with production deferred to the roadmap.

## Decision
We **ship a lean MVP on Python + FastAPI + SQLite + vanilla-JS, as one modular monolith on a
shared FHIR substrate, with production concerns explicitly deferred**. The reference build
already runs offline, so the hours buy product, not plumbing (`backend/main.py`,
`requirements.txt`). The MVP has **no auth, encryption, audit, RBAC, or retention** — synthetic
data only; PHIPA governs real data and is out of scope. Both product directions — Patient
Context Board (`/board`) and Office Assistant (`/office`) — ship on the one substrate because
the shared `fhir.*` layer makes the second direction cheap, not because scope was widened. The
production stack (.NET 8 + PostgreSQL + RBAC/audit/encryption) is the documented roadmap
(ADO AB#615), not this build.

## Consequences
- **Positive:** fastest path to a working, laptop-deployable, fully-offline demo with full UI
  control; reuses tested code; one architecture quantum (single app, one SQLite store,
  synchronous calls), so it is simple to reason about and rehearse.
- **Negative:** Python/vanilla-JS is not the team's primary stack and has no component
  framework; the app is **not deployable against real PHI** until the production story is built.
- **Trade-off accepted:** we spend nothing on production controls now (wrong investment depth
  for a kill-gated demo) and carry .NET/Postgres only as a roadmap story.

## Compliance
**Kill/scope gate:** production controls are added only when the bet is greenlit past the demo;
until then build depth stays minimal and reversible. **Fitness mechanism:** the layered
modular monolith (`API → service → modules`; modules never import the API layer) keeps the
two UIs separable and the production migration path open. Scalability/performance are explicit
non-goals (single-user demo).

## Notes
Author: project lead · Approvers: architect / review board · Last modified: 2026-06-20.
Supersedes: none. Superseded by: none. Source decisions: `docs/design/DESIGN.md`
"Python + FastAPI + SQLite + vanilla-JS stack" and "Lean MVP vs a separate production story".
