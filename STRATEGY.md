# Strategy — Loop @ AI in Healthcare Co-Design Hackathon

Grounded in the event **Developer Guide** (COMPASS program, uOttawa DFM · TOH DFP ·
Bruyère · AGI Ventures). This is the plan that ships with the code.

## The problem
Family physicians lose ~19 hours/week to admin work, over half report burnout, and
nearly 1 in 5 Canadians has no regular primary-care provider. COMPASS (Consensus On
Medical Priorities and AI Solutions in Primary Care, part of NAVIGATOR) spent a year
in clinician priority-setting. The core message: **don't replace clinical judgement —
reduce repetitive work, support preparation and follow-through, protect continuity.**

## The six clinician challenge areas
You may build any of them; pick what you can prototype credibly.

1. Pre-visit preparation
2. Encounter support & point-of-care reasoning
3. Medication & prescribing support
4. **Follow-up & care-plan automation**
5. **Administrative & coordination automation** — *"where AI should start"*
6. Continuity & whole-person intelligence

## What we're building — and why
**Path 2 — a Digital Medical Office Assistant** (challenge area #5, the experts' #1
ranked idea), with follow-up task creation (#4). Three moves:

1. **Necessity gate** — classify every inbound request *before* drafting anything:
   `eliminate / delegate / automate / physician_review`. Most paperwork doesn't need
   a physician at all; that work never reaches the desk.
2. **Form prefill** — for requests that do need a physician, pre-fill the known fields
   from the chart/FHIR with **evidence + confidence**; genuine clinical-judgement
   fields (functional limitations, prognosis, work capacity) are **flagged for the
   physician, never invented**. Approval generates a **draft + a follow-up task**.
3. **Measured moment** — minutes saved, physician touchpoints avoided, projected
   hours/year and FTE recovered.

Why Path 2: it is "where AI should start," it is the easiest to make **visibly
actionable** (the Guide: *"don't just generate text — convert decisions into tasks:
draft the referral, queue the follow-up, prepare the form"*), and the saved-minutes
metric maps straight onto the clinical-importance judging criterion.

**Alternative — Path 1 (Patient Context Board)** for pre-visit prep + continuity
(challenge areas #1 + #6) is equally valid, runs on the *same foundation*, and the
Guide explicitly says to choose on team fit. Switching is cheap.

## How it scores against the four judging criteria
| Criterion | How this build answers it |
|---|---|
| **Clinical importance** | Admin burden is the measured, #1-ranked pain; the metric quantifies the time returned |
| **Technical feasibility** | FHIR-native, standard stack, runs on a laptop; realistic to deploy in 6–12 months |
| **Safety & privacy** | Local processing, synthetic data only, AI restates source-backed facts and never invents clinical content, deterministic fallback, physician approves everything |
| **Workflow fit** | "No new login" framing, fewer clicks, converts decisions to tasks, integrates via FHIR |

## Design requirements satisfied
Actionable outputs (draft + task) · low cognitive burden (only physician-review items
reach the MD) · calibrated trust (confidence + evidence + edit/override) · proactive ·
**practical affordability** (lean local stack, no expensive infrastructure) · privacy by
design (local, synthetic, data minimization).

## Architecture
The shared **FHIR foundation** (scan → snapshot → diff → safe, source-backed summary)
plus the **office assistant** (necessity gate → form prefill → metrics). Stack:
FastAPI + Pydantic + Ollama (local, optional) + SQLite + httpx; single-file vanilla-JS
UIs; mock/deterministic fallbacks so the demo never fails on stage. See `FOUNDATION.md`
to run it. UIs: `/` (follow-up extractor), `/office` (office assistant).

## Today → tomorrow
- **Today (5+ hrs prep):** run the offline demos; `ollama pull` + judge real extraction
  quality; stand up Synthea → local HAPI; finalize the form(s); write the privacy
  one-pager, demo script, and SME questions.
- **Tomorrow (event):** confirm focus with the clinician SMEs at the 9:30 panel; build
  the chosen branch's actionable + measured moment; rehearse the demo ×2; keep mock as
  the safety net.

## Demo script (~90 seconds)
1. Inbox: a **sick-note** request → the necessity gate says *doesn't need a physician* →
   patient attestation. *"We don't speed up the paperwork — we keep it off your desk."*
2. A **Disability Tax Credit** request → physician review → fields pre-filled from the
   chart with evidence; functional limitations & prognosis flagged for you; you complete
   them, approve → **draft + follow-up task** created.
3. The **metric strip**: minutes saved, touchpoints avoided, projected hours/FTE — all
   local, all synthetic.

## Kill / pivot
- **Kill:** if nothing runs even in mock one hour before the demo → static run + slides.
- **Pivot:** if one form is dull on rehearsal → add a second (reuse rate), or switch to
  Path 1 (Context Board) on the same foundation.

## Guardrails
Synthetic / de-identified data only. Not a medical device. No diagnosis, treatment, or
prescribing automation. The physician approves every clinical output. Real PHI is
governed by PHIPA.
