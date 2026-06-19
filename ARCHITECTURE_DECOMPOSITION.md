# Architecture Decomposition Brief — Loop

**For:** the architect doing decomposition + task assignment for the event-day build.
**Companion docs:** `STRATEGY.md` (scope & why), `FOUNDATION.md` (how to run + the FHIR
layer), `docs/blueprint.html` (what/why one-pager), `docs/architecture.mermaid` (C4
container diagram). **The code is the authoritative interface spec** — `backend/main.py`
defines the HTTP contracts, `backend/schema.py` + `backend/office/forms.py` define the
data models.

---

## 0. TL;DR
One **architecture quantum** — a local **modular monolith**. Decompose *logically* along
the existing module seams + HTTP/Pydantic contracts; do **not** split into services.
Top-3 driving characteristics: **auditability, privacy/locality, simplicity**. The work
parallelizes into four streams behind stable contracts. Hand the architect this brief +
the repo; everything they need to cut work is already in the seams.

## 1. Scope & quantum
Single independently-deployable app, runs locally, one SQLite store, synchronous internal
calls → **one set of characteristics → modular monolith**, not microservices. This is a
deliberate trade-off for affordability + a one-day build. Decomposition is therefore
**logical (modules)**, not physical (services). Don't reach for a distributed style.

## 2. Driving architecture characteristics (the decomposition drivers)
Pick the trade-offs we can live with — least-worst, not "best." Top 3 starred.

- ★ **Auditability / explainability** — the whole safety story. Drives the "source-backed
  + evidence + confidence + physician-review" boundary; nothing the AI emits is unsourced.
- ★ **Privacy / data locality** — drives "no PHI leaves the machine, local model, synthetic
  data only."
- ★ **Simplicity / feasibility** — drives "no heavy infra, laptop-deployable, fallbacks."
- **Modularity** — drives the port seams (swap FHIR source / model / form; parallelize team).
- **Reliability / demonstrability** — drives the mock/deterministic fallbacks (demo can't fail).
- *Not drivers:* scalability, performance, elasticity (single user, demo). **Do not optimize
  for them** — every extra characteristic adds complexity for no benefit here.

Explicit trade-off: we trade scalability/performance away in favour of simplicity +
auditability. Say so out loud in the decomposition.

## 3. Logical components (current decomposition)
Leaf directories are the components. Names are **functional, not entity-based** (no
`Manager`/`Engine` dumping grounds). Watch role statements for "and" — none should need it.

| Component (dir/module) | Single responsibility | Public interface | Depends on | Cohesion |
|---|---|---|---|---|
| API (`backend/main.py`) | HTTP boundary; route to services | the endpoints (§4) | fhir.service, office.service, llm | functional |
| FHIR · client | pull patients/resources from a FHIR R4 base | `FHIRClient.scan()` | httpx, external FHIR | functional |
| FHIR · normalize | content hash with volatile meta stripped | `content_hash`, `patient_ref` | — | functional |
| FHIR · store | persist/load resource snapshots | `create_scan_run`, `load_snapshot_map` | sqlite3 | functional |
| FHIR · diff | classify new/updated/unchanged/not_returned | `classify` | normalize | functional |
| FHIR · summarize | safe, source-backed board + safety filter | `summarize` | (optional) Ollama | functional |
| FHIR · service | orchestrate scan→snapshot→diff→summary | `run_scan`, `diff_last_two`, `build_context` | the above | sequential |
| Office · necessity | route a request (eliminate/delegate/automate/review) | `classify` | — | functional |
| Office · forms | canonical record + form registry + prefill | `build_functional_limitations`, `prefill_form` | schema | functional |
| Office · metrics | saved-minutes / touchpoints / FTE | `per_task`, `project_annual` | — | functional |
| Office · service | orchestrate triage→prefill→metrics | `get_queue`, `prefill_request`, `project` | necessity, forms, metrics, llm | sequential |
| Extractor (`schema` + `llm` + `mock`) | note → `EncounterExtraction` (+ fallback) | `llm.extract` | (optional) Ollama | functional |
| UIs (`frontend/`) | `index.html` (follow-up), `office.html` (office assistant) | the HTTP API | API | — |

Architecture style read: **layered** (API → service → modules; modules never import the API).
That layering is the main invariant to preserve when assigning work.

## 4. The seams to decompose along (contracts)
These are the stable interfaces teams work *behind* — keep cross-boundary coupling weak
(JSON/Pydantic = Name/Type connascence only).

**HTTP API (the integration contract):**
| Method · Path | Body → Response |
|---|---|
| `GET /api/health` | → model/host/mode |
| `POST /api/extract` | `{note, sample_id?}` → `{mode, extraction}` |
| `POST /api/fhir/scan` | `{source, which?, base_url?, patient_count}` → `{scan_run_id, source, resource_count, patients}` |
| `GET /api/fhir/diff` | → `{status, prev/curr_scan_id, diff}` |
| `GET /api/fhir/patients` | → `[{id, name}]` |
| `GET /api/fhir/context/{id}` | → `{status, mode, board}` |
| `POST /api/fhir/reset` | → `{status}` |
| `GET /api/office/requests` | → triaged queue `[{…, route, reason, who, metrics}]` |
| `POST /api/office/prefill` | `{request_id}` → `{status, route, mode, patient_context, form}` |
| `POST /api/office/metrics` | `{processed:[{category, route}]}` → projection |

**Data models (the shared vocabulary):** `EncounterExtraction` (`backend/schema.py`); the
canonical `FunctionalLimitations` record + form registry (`backend/office/forms.py`);
FHIR resource JSON; the diff-result shape (`backend/fhir/diff.py`).

**Ports (swappable — natural parallelization points):**
- **FHIR source** — `FHIRClient` (fixtures ↔ live HAPI/Synthea)
- **LLM** — Ollama client ↔ mock/deterministic
- **Storage** — SQLite snapshot store

## 5. Current build state
- **Done & tested (offline):** FHIR foundation, office assistant, both UIs, mock/deterministic
  fallbacks, every endpoint.
- **To do (event day):** stand up live Synthea → local HAPI; real-model quality pass; finalize
  the chosen form(s) with SMEs; rehearse.
- **Stretch:** Path 1 (Patient Context Board) UI on the same foundation; FHIR
  QuestionnaireResponse export; a 2nd form (reuse rate).

## 6. Work breakdown — parallelizable streams (~3–4 productive hours)
The seams are stable, so these run independently and integrate at the HTTP API:

- **Stream A — Data/FHIR:** Synthea → local HAPI; validate the live scan path. *Contract:* FHIR source port. Can start immediately.
- **Stream B — Office/forms:** finalize form(s), prefill mapping, necessity rules. *Contract:* forms registry + `/api/office/*`. **Blocked on SME input (9:30 panel).**
- **Stream C — Model/safety:** `ollama pull`; extraction/summary quality; tune the safety filter. *Contract:* extractor + summarizer. Can start immediately.
- **Stream D — UI/demo:** polish `office.html`, the metric panel, the demo flow; rehearse. *Contract:* HTTP API. Integrates last.

Sequencing: **A + C start now**, **B after the 9:30 SME panel**, **D integrates last**. The
HTTP API is the meeting line — freeze it early. (Solo fallback order: C → B → D; A as stretch.)

## 7. Open architecture decisions (decide fast — record as ADRs; *why* > *how*)
| ADR | Decision | Options | Recommendation | Decide by |
|---|---|---|---|---|
| 1 | Demo data source | fixtures · live Synthea→HAPI | controlled Synthea→HAPI (real diff/prefill, you control the change) | pre-event |
| 2 | Summary/extraction engine on stage | local model · deterministic/mock | carry both; choose by quality at rehearsal | rehearsal |
| 3 | Which form(s) first | DTC · sick note · insurance STD | whichever SMEs call most painful | 9:30 panel |
| 4 | Scope | Path 2 only · + Path 1 sliver | Path 2 only for one day | now |

## 8. Fitness functions (keep the decomposition honest)
- **No cyclic dependencies** across `core ↔ fhir ↔ office`; modules must not import the API layer (preserve the layering).
- **"AI invents nothing"** characteristic → the safety post-filter (`summarize._passes_safety`) *is* the fitness function: any model text with clinical wording is rejected and the deterministic summary used. Keep it; add tests.
- Keep the **mock/deterministic fallback paths** working (reliability/demonstrability), and cyclomatic complexity modest (≤10).

## 9. Decomposition guardrails (what NOT to do)
- Don't split into microservices or add pgvector / a HAPI cluster / .NET — it violates the
  **simplicity/affordability** characteristic *and* the time budget. It is **one quantum**.
- Don't let the AI emit clinical content — preserve the **source-backed + physician-review** boundary.
- Don't break the fallbacks (demo safety).
- Keep cross-module coupling weak — talk through the JSON/Pydantic contracts, never internals.
