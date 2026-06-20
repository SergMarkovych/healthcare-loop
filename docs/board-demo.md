# Demo script — Patient Context Board (Direction A, Mini-MVP)

The pre-visit "what changed since last visit" board. Same FHIR engine as the Office
Assistant, same safety rule: **every line restates a FHIR-API fact and cites its source;
no diagnosis, prognosis, or interpretation is generated.** Open **`/board`**.

> One-liner: *"Before the patient walks in, the physician gets a one-screen board of what
> changed and what's worth a glance — assembled from the chart, every line traceable, and
> nothing the AI made up."*

## Beat 1 — load + pick a patient (~15s)
Click **Load synthetic scans** (runs two FHIR scans on the fixtures), then pick **Jordan
Sample**. The board assembles from `GET /api/board/synthetic-A`.

## Beat 2 — the three cards (~45s)
- **Patient snapshot** — demographics, active condition (Type 2 diabetes), current
  medication (Metformin), last visit. Each line cites its FHIR resource.
- **Worth a glance** — deterministic flags only: *"Metformin dose changed: 500 mg twice
  daily → 1000 mg twice daily"* (the exact field change since last scan), plus current
  observations stated verbatim (A1c = 8.4 %, Creatinine = 92 umol/L). *Note what it does
  NOT do — it never calls a value normal or abnormal; that judgement is the physician's.*
- **Review queue** — what changed since the last scan (new / updated / not-returned) and
  any open workflow tasks, as an actionable list.

## Beat 3 — the safety line (~10s)
Point at the footer: *"Every line restates a FHIR-API fact and cites its source. No
diagnosis, prognosis, or interpretation is generated."* That is the whole trust story —
the board organizes source-backed facts, the physician supplies the judgement.

## Verified
`tests/test_board.py` (12 cases) asserts the card contents and that no interpretive wording
leaks; the render is browser-verified (3 cards, source refs, the dose-change line). The
board also runs against live HAPI patients (`scripts/load_local_hapi.sh`).
