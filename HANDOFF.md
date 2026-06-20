# Handoff — HealthCare "Loop" (pick up here)

_Last updated: 2026-06-20. Repo: https://github.com/SergMarkovych/healthcare-loop (private)._

## Get it running (fresh machine)
```bash
git clone https://github.com/SergMarkovych/healthcare-loop.git
cd healthcare-loop
python -m venv .venv && .venv/Scripts/activate   # (Win) | source .venv/bin/activate (mac/linux)
pip install -r requirements.txt -r requirements-dev.txt
python run.py            # -> http://127.0.0.1:8000   ( /board , /office , / )
python -m pytest -q      # 102 passed, 2 skipped
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

## ✅ AB#648 — DONE (Office Assistant guided wizard + follow-up fixes)
`/office` was "not usable / feels fake"; a `/critic-senior` pass confirmed it. **Fixed:** rebuilt
as the 5-step guided wizard in `docs/design/office-wizard.md` (Triage → Your desk → Review →
Approve → Done payoff with artifact ledger). Pure client-side state machine over the existing
`/api/office/*` endpoints — no backend change. Also removed the contradictory `sick_note` from
`forms.FORMS`. **Browser-verified** (Playwright) through all 5 steps at 1280px **and** 800px —
zero JS errors, clean single-column reflow. Lesson applied: *green tests prove it RUNS; viewing
the render proves it's USABLE.* (commit `a04faab`)

**Follow-up fixes (commit `1231581`):**
- **Metrics bug fixed** — the payoff strip re-summed minutes/touchpoints client-side via a
  type-fragile request-id lookup that diverged from the headline (showed 13/1 vs "6 of 6").
  Now uses the backend's authoritative `minutes_saved_now` / `physician_touchpoints_avoided`
  → **49 min / 3 touchpoints**, consistent with the headline.
- **a11y** — `<label for>`↔input id associations; counter `aria-live="polite"`; `role="alert"`
  on the safety-bounce message; focus moves to the step heading on each transition.
- **Verified (Playwright, viewed):** safety bounce on a blanked clinical field shows the alert,
  focuses the field, does **not** advance; `WRITE_ENABLED` ledger renders 3 "Written to FHIR"
  rows with `Task/` + `QuestionnaireResponse/` locations.
- **Container build verified** — `docker compose up --build` builds `healthcare-loop:latest`,
  runs **healthy**, serves the fixed wizard, and `force_mock=true` offline (prefill falls back to
  `mock`, no Ollama needed). `docker compose --profile live up` adds a local HAPI on :8080.

No open tasks. The local MVP is complete and usable. Only remaining non-blocking polish: the
"Model: llama3.1" chip shows even when Ollama isn't running (summaries still fall back to
deterministic) — see `SESSION-SUMMARY.md`. AB#648 closed in ADO (State=Done + audit comment).

## Deferred (roadmap, AB#615) — only if asked
SMART on FHIR, CDS Hooks, Health Canada DPD/CCDD, MIMIC-IV, MTSamples, production stack
(.NET 8 + PostgreSQL + RBAC/audit/encryption). Not bugs — intentional non-goals for a local MVP.

## Reference: `ARCHITECT_START_HERE_3\compass-followup-copilot` is an OLDER branch — loop is ahead
on everything shared; only its write-back trio + ADRs were worth cherry-picking (already done).
