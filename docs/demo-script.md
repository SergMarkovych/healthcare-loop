# Demo script — Office Assistant (Direction B) · ≈90 seconds

Runs in **mock / deterministic mode** — no model, no network. The demo cannot fail on
stage. Open **`http://127.0.0.1:8000/office`**.

> One-liner to open with: *"Family physicians lose ~19 hours a week to admin, and over
> half of it doesn't need a physician at all. We don't speed up the paperwork — we keep
> it off the desk, and for what's left we pre-fill everything safe and flag only what
> needs your judgement."*

## Beat 1 — the necessity gate (~25s)
The inbox shows a triaged queue. Point at the **sick-note** request:

- Route: **eliminate** → *"In Ontario an employer can't require a sick note for ESA
  leave. This resolves with a patient attestation — it never reaches your desk."*
- Contrast with the **prescription renewal (stable)** → **automate** (pharmacist /
  protocol) and the **monitoring bloodwork** → **automate** (standing order).

Most of the queue is gone before any drafting happens. *That* is the saved time.

## Beat 2 — safe form prefill (~40s)
Open the **Disability Tax Credit (T2201)** request → route **physician_review**.

- **Auto-filled from the chart** (each with evidence + confidence): patient name, date
  of birth, diagnosis (Type 2 diabetes). *"Pulled from the FHIR record, not typed."*
- **Flagged for you, left blank** (never invented): **onset date**, **functional
  limitations**, **prognosis**. *"These need clinical judgement, so the AI refuses to
  guess them — it hands them to you."*
- Complete the three clinical fields → **Approve** → a **draft + a follow-up task** are
  created. *"The decision becomes an action, not just text."*

This is the safety story: the AI restates source-backed facts and stops at the line
where judgement begins.

## Beat 3 — the measured moment (~25s)
Show the **metric strip**: minutes saved on this batch, physician touchpoints avoided,
and the projection — **~182 hours/year per physician**, ~10 FTE per 100 physicians.

*"Local, synthetic, auditable. Every number traces to a routed request. Nothing left
the machine."*

## If something breaks
The whole flow is deterministic and offline; there is no live dependency to fail. If the
UI itself misbehaves, fall back to the API calls in [`FOUNDATION.md`](../FOUNDATION.md)
and narrate the JSON.
