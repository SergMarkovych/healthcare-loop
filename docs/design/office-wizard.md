---
status: proposed (ready to build)
app: HealthCare
feature: Office Assistant — guided wizard redesign
created: 2026-06-20
---

# Office Assistant — Guided Wizard Redesign

**Why:** real users found the current `/office` "not usable" — *confusing (don't know what
to do)* and *feels pointless/fake*. A `/critic-senior` review confirmed it (file:LINE
evidence): almost every action renders its result in an off-screen right panel nothing
points at; the first card (sick note) is a silent dead-end; cold-start shows `0/0/0/0` with
no "start here"; below 900px the form stacks under the whole queue.

**Fix:** a **linear client-side wizard** over the *same* backend endpoints — no backend
change. It does the necessity gate's thinking out loud, separates "not yours" from "yours,"
and makes every resolution produce a *visible artifact*.

## Progress model (always visible)
A sticky **step rail** under the header (replaces the cold metrics strip as the first thing
seen): `①Triage → ②Your desk → ③Review & complete → ④Approve → ⑤What you saved`, current
highlighted, done checked. Steps 3–4 repeat per physician item ("Review · item 1 of 2"). A
one-line "you are here" caption changes per step. **The metrics strip moves to Step 5 only**
— it never greets the user at 0.

## Steps
1. **Triage the inbox.** Show all 6 requests as *the gate doing its job*, grouped: **"Handled
   without you (4)"** (eliminate/delegate/automate — presented as already-decided, route pill
   + who + saves-min) and **"Needs your clinical judgement (2)"** (the `physician_review`
   items, amber-elevated). ONE action: **"Clear the 4 automatic items →"** resolves all four
   in sequence (each flashes ✓ "attestation issued / routed / generated" *in place on the
   card*), then advances. Copy: *"The necessity gate sorted your inbox. Most of it never
   needed you."* API: `GET /api/office/requests`.
2. **Your desk.** Only the 2 physician items as a numbered worklist ("2 forms need your
   clinical input"); the 4 cleared collapse to a quiet "✓ 4 handled — 47 min saved" row. ONE
   action: **"Start with [first form] →"**. No new API.
3. **Review & complete.** The prefilled form, **re-sequenced so physician fields come first**
   under "Your input needed (N)", with "Pre-filled from the chart (M) ▸" collapsed below
   (auto fields keep confidence pill + evidence). Live counter "2 of 3 clinical fields
   complete". ONE action: **"Approve & generate →"** — *disabled until all physician fields
   are filled* (label: "Complete 1 more field to approve"). API: `POST /api/office/prefill`.
4. **Approve (safety gate).** Pressing approve in Step 3 *is* Step 4. Happy path: `complete:true`
   → per-item success → next item or Step 5. **Safety case (most important):** client-gate makes
   a blank clinical field un-submittable; the server `outstanding_fields` check stays as the
   authoritative net — if it returns `complete:false`, the wizard does NOT advance; it bounces
   to the named field with *"Can't finish yet — [Prognosis] still needs your clinical judgement.
   We never fill this for you."* Draft saved as incomplete, nothing lost, not counted as cleared.
   API: `POST /api/office/approve`, branch on `res.draft.complete`.
5. **What you saved (payoff).** Kills "feels fake". Top→bottom: headline **"You cleared 6 of 6
   requests"**; an **artifact ledger** — one row per resolved request showing *what now exists*:
   physician forms → "📄 DTC draft ready" + "↳ Task created…" + (WRITE_ENABLED) "↪ Written to
   FHIR: Task/… · QuestionnaireResponse/…"; automatic items → "✓ Sick note — attestation issued",
   etc.; then the **metrics strip animating 0→N** (minutes saved / touchpoints / hrs-yr / FTE)
   — now meaningful because the user watched the work happen. Closing line: *"Every draft and
   task above is real output your staff can act on now."* API: `POST /api/office/metrics` once.

## Make automatic items visibly resolve (the #1 "nothing happened" cause)
Relocate `showHandled`'s result text from the off-screen `#review` panel to **in-place on the
card** at clear-time (teal check sweep, route pill → "✓ Issued/Routed/Generated", one-line
result on the card), echo into the Step-5 ledger. No backend change.

## Reuse contract (NO backend changes)
| Step | Endpoint (unchanged) | JS to reuse |
|---|---|---|
| 1 | `GET /api/office/requests` | `renderQueue` (regroup by route), `onAction` non-physician branch, `showHandled` (relocate) |
| 2 | — | `markDone`/`processed` map |
| 3 | `POST /api/office/prefill` | `prepareForm`/`renderForm`, reorder fields by `needs_physician` |
| 4 | `POST /api/office/approve` | `approveForm`, branch on `draft.complete` |
| 5 | `POST /api/office/metrics` | `updateMetrics`/`project`, draft+task+FHIR render |

All design tokens/components reused (`:root`, `.btn`/`.field`/`.route`/`.result`). It's a
client-side state machine (`step`, `physicianQueue`, `cursor`) over the existing fetch calls —
no router, no framework, consistent with the current vanilla `"use strict"` script.

## Backend bug to fix in passing (from the critic)
`sick_note` routes `eliminate` (no form) yet `has_form:true` and `prefill` builds a sick-note
form; `expected_duration` returns the literal string `"see note"`. Decide: drop `sick_note`
from `forms.FORMS` (it's truly eliminate) — `backend/office/forms.py:90-93`, `data.py:8`.

## Build via: design → build agent → browser-verify (Playwright, viewed at real viewports).
