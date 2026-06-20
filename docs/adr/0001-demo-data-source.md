# ADR-0001: Demo data source — offline fixtures vs live HAPI, and FHIR as the single runtime API

- **Status:** Accepted
- **Proposed:** 2026-06-20 · **Accepted:** 2026-06-20
- **Deciders:** project lead, architect

## Context
The FHIR foundation can source a scan three ways: (a) **offline fixtures** (deterministic
synthetic scans bundled in the repo), (b) a **local HAPI FHIR server loaded with Synthea**
(real FHIR R4 API calls, with controlled change between scans), or (c) the **public HAPI
test server** (real API, shared/uncontrolled data). The demo needs a credible "what changed /
source-backed context" moment, and a top risk is that a live scan produces nothing
interesting or fails to connect on the day. A related decision was whether to wire any second
runtime API (SMART on FHIR, CDS Hooks, Health Canada DPD-CCDD, MIMIC-IV, MTSamples) now.

Alternatives: (a) fixtures only; (b) live HAPI primary, fixtures fallback; (c) public HAPI
live only; and for the API surface, (d) FHIR R4 only vs (e) multi-source now.

## Decision
We **default to offline fixtures and keep live HAPI as an optional mode**, with **FHIR R4
REST as the single runtime API for the MVP**. One external API (`backend/fhir/client.py`) is
pointed via `FHIR_BASE_URL` (`backend/fhir/service.py:19`) at public HAPI, a local
HAPI+Synthea, or the bundled fixtures (`backend/fhir/fixtures/scan_1.json` / `scan_2.json`).
The whole app ships as **one Docker container that runs fully offline by default**
(`FORCE_MOCK=1`, `FORCE_DETERMINISTIC=1`); a `--profile live` compose profile starts a local
HAPI on `:8080` for the controlled scan → change → re-scan → field-level diff walkthrough.
Wiring any additional runtime API is deferred to the production roadmap (ADO AB#615).

## Consequences
- **Positive:** the offline default removes the "no change to show" and "server down on stage"
  risks; `docker compose up --build` reproduces the full scan → diff → board flow with no
  network or model. FHIR-only keeps the blast radius small — one auth/shape to get right.
- **Negative / cost:** carries two code paths (fixtures + live); a multi-source config
  registry (`config/sources.json`, 3 active FHIR + 6 roadmap stubs) exists but the roadmap
  sources are stubs, not live integrations.
- **Trade-off accepted:** live HAPI is the richer "real FHIR-API integration" story but is
  optional, traded for a guaranteed-repeatable offline demo.

## Compliance
`FOUNDATION.md` and `docs/DEPLOY.md` document both paths. **Fitness check:** the offline path
is the Docker default and is exercised by the 66-test suite (scan / content-hash diff /
`/metadata` gate / Bundle pagination); live HAPI scan/diff/context was verified by curl.
**Toggles:** `FHIR_BASE_URL` selects the live server; `source: "fixtures"` (or the default
offline flags) forces the bundled path. Synthetic / de-identified data only — no PHI.

## Notes
Author: project lead · Approvers: architect / review board · Last modified: 2026-06-20.
Supersedes: none. Superseded by: none. Source decision: `docs/design/DESIGN.md`
"FHIR as the single runtime API for the MVP" + "Content-hash diff" decision blocks.
