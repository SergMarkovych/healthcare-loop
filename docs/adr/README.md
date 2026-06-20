# Architecture Decision Records (ADRs)

Short records of architecturally significant decisions for the HealthCare "Loop" build.
Format follows Richards & Ford (*Fundamentals of Software Architecture*, 2nd ed.): **Title ·
Status · Context · Decision · Consequences · Compliance · Notes**. Decisions are written in
active voice; alternatives live in Context; trade-offs in Consequences; governance in
Compliance.

ADRs 0001–0004 record decisions Loop **already made and shipped**. ADRs 0005–0006 record the
COMPASS SME-panel direction for the `/office` agent-farm flow (Epic AB#662) — Accepted and now
being built. Each ADR cites the `<decision>` block in `../design/DESIGN.md` it derives from (or
the COMPASS deliverables under `../original/ExpertSays/`) and the `backend/` files that implement it.

| # | Decision | Status | Implemented in |
|---|---|---|---|
| [0001](0001-demo-data-source.md) | Demo data source — fixtures offline-default, optional live HAPI, FHIR as the single runtime API | Accepted | `backend/fhir/client.py`, `service.py:19`, `fixtures/`, Docker |
| [0002](0002-summarization-engine.md) | Summarization engine — deterministic builder + safety post-filter, optional Ollama | Accepted | `backend/fhir/summarize.py:22-27,111-153` |
| [0003](0003-rules-and-form-scope.md) | Rules + form scope — data/workflow flags, not medical rules; modular form registry | Accepted | `backend/fhir/rules.py:41-67`, `backend/office/forms.py` |
| [0004](0004-build-scope.md) | Build scope — lean MVP (Python/FastAPI/SQLite/vanilla-JS, one shared substrate) vs production stack | Accepted | `backend/main.py`, `requirements.txt` |
| [0005](0005-office-agent-decomposition.md) | `/office` agent-farm — narrow agents + deterministic-flow orchestration + verification layer; canonical-record form seam kept (reconciles ADR-0003) | Accepted | planned (AB#662): `backend/office/{verifier,summarizer}.py`, `office/service.py` |
| [0006](0006-lead-form-priority.md) | Lead form — referral intelligence leads, carried by form auto-fill, framed by the necessity gate; inbox/billing roadmap | Accepted (pending SME freq.) | `backend/office/referral_intel.py` |

**Status lifecycle:** `Proposed` → `Accepted` → `Superseded by N`. A proposed ADR is modified
until accepted; once accepted it can later be superseded by a new, higher-numbered ADR (which
notes `supersedes N`). The deferred production stack (.NET 8 + PostgreSQL + RBAC/audit) and
additional runtime APIs (SMART on FHIR, CDS Hooks, DPD-CCDD, MIMIC-IV, MTSamples) are roadmap,
tracked under ADO AB#615 — a future ADR would record those when built.
