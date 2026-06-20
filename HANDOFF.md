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

## ⏭ THE open task — AB#648 (do this next)
**`/office` is NOT usable for a real user** — confusing ("don't know what to do") + feels
pointless/fake. A `/critic-senior` review confirmed it (results render in an off-screen panel;
first click is a silent dead-end; cold-start = 0/0/0/0; form stacks below the queue on narrow
screens). **Fix = build the guided wizard** fully specified in **`docs/design/office-wizard.md`**
(5-step client-side flow over the *same* endpoints, no backend change). Also fix the `sick_note`
eliminate-vs-`has_form` contradiction (`backend/office/forms.py:90-93`). Then **browser-verify
at real viewports (1366px + 800px)** — not just curl/pytest. Lesson from this build:
*green tests/curl prove it RUNS, not that it's USABLE; verify the rendered experience.*

## Deferred (roadmap, AB#615) — only if asked
SMART on FHIR, CDS Hooks, Health Canada DPD/CCDD, MIMIC-IV, MTSamples, production stack
(.NET 8 + PostgreSQL + RBAC/audit/encryption). Not bugs — intentional non-goals for a local MVP.

## Reference: `ARCHITECT_START_HERE_3\compass-followup-copilot` is an OLDER branch — loop is ahead
on everything shared; only its write-back trio + ADRs were worth cherry-picking (already done).
