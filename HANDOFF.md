# Handoff — HealthCare "Loop" (pick up here)

_Last updated: 2026-06-20. Repo: https://github.com/SergMarkovych/healthcare-loop (private)._

## Get it running (fresh machine)
```bash
git clone https://github.com/SergMarkovych/healthcare-loop.git
cd healthcare-loop
python -m venv .venv && .venv/Scripts/activate   # (Win) | source .venv/bin/activate (mac/linux)
pip install -r requirements.txt -r requirements-dev.txt
python run.py            # -> http://127.0.0.1:8000   ( /board , /office , / )
python -m pytest -q      # 90 passed, 2 skipped
# or fully containerized:  docker compose up --build
```
Synthetic data only, runs fully offline. See `docs/DEPLOY.md`, `docs/live-fhir-demo.md`.

## State (what's done)
Local MVP, all pushed, 90 tests + 2 skipped, GitHub Actions CI green:
- **Patient Context Board** (`/board`): activity list (10/page pagination), 5-card board,
  rules/flags audit card, sources registry, WCAG-AA UI, cross-tool nav. Live-FHIR verified.
- **Office Assistant** (`/office`): necessity gate → prefill → approve → draft+task → metrics;
  FHIR write-back loop (mock-safe; verified live with `WRITE_ENABLED`).
- Docker, ADRs (`docs/adr/`), system design (`docs/design/DESIGN.md`).
- ADO project **HealthCare** (org sandbox-mydev), Epics 580/600/610/631/639/644 closed.

## ✅ AB#648 — DONE (Office Assistant guided wizard)
`/office` was "not usable / feels fake"; a `/critic-senior` pass confirmed it. **Fixed:** rebuilt
as the 5-step guided wizard in `docs/design/office-wizard.md` (Triage → Your desk → Review →
Approve → Done payoff with artifact ledger). Pure client-side state machine over the existing
`/api/office/*` endpoints — no backend change. Also removed the contradictory `sick_note` from
`forms.FORMS`. **Browser-verified** (Playwright) through all 5 steps at 1280px **and** 800px —
zero JS errors, clean single-column reflow. See `SESSION-SUMMARY.md` for the full rundown.
Lesson applied: *green tests prove it RUNS; viewing the render proves it's USABLE.*

No open tasks. The local MVP is complete and usable. Optional non-blocking polish noted in
`SESSION-SUMMARY.md` (step-5 metrics vs headline; Ollama model chip).

## Deferred (roadmap, AB#615) — only if asked
SMART on FHIR, CDS Hooks, Health Canada DPD/CCDD, MIMIC-IV, MTSamples, production stack
(.NET 8 + PostgreSQL + RBAC/audit/encryption). Not bugs — intentional non-goals for a local MVP.

## Reference: `ARCHITECT_START_HERE_3\compass-followup-copilot` is an OLDER branch — loop is ahead
on everything shared; only its write-back trio + ADRs were worth cherry-picking (already done).
