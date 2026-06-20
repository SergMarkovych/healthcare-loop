# Loop — local-first follow-up co-pilot

> **Synthetic data only.** This is a prototype — do not load real patient data (PHI).
> Every sample note and patient record in this repository is fabricated. Real PHI is
> governed by PHIPA (Ontario) and is deliberately out of scope. Bring your own LLM API
> key via a local `.env` (never committed); none is shipped in this repo.

A hackathon scaffold for **Hackers & Healers | AI in Healthcare** (Ottawa).
It turns a free-text primary-care encounter note into a **structured, reviewable
follow-up plan** — with a clinician approving or editing every item before anything
is "saved." It can run fully on-device (local Ollama) or against a hosted model
(OpenRouter) — see the privacy note and LLM provider options below.

This is a starting point, not a finished product. It's wired end-to-end so your
team spends the day on the idea, not the plumbing.

---

## Why this shape (read before you build)

The brief comes from **COMPASS** (*Consensus On Medical Priorities and AI Solutions
in Primary Care*), a year-long priority-setting program with practicing family
physicians. The signal from clinicians was clear:

> They don't want AI to replace clinical judgement. They want tools that reduce
> repetitive work, support preparation and follow-through, and protect continuity
> of care.

This scaffold is deliberately built around that:

- **Reduces repetitive work** — drafts the structured follow-up from the note.
- **Supports follow-through & continuity** — every test, referral, and task is
  captured with an owner and a timeframe, so nothing falls through the inbox.
- **Keeps the human in charge** — nothing is auto-committed. Each AI suggestion is
  a *proposal* the clinician approves, edits, or removes. The export contains only
  what a human signed off on, with an audit trail.
- **Local-first is supported, but not the only mode — be precise about this.**
  In **Option A** (local Ollama) extraction runs on-device and no encounter text
  leaves the machine. In **Option B** (OpenRouter, the default in `docker-compose`)
  the encounter note *is* sent to a hosted model, and **voice dictation always sends
  audio to OpenRouter** regardless of the text provider. Pick the mode that matches
  your privacy posture and state it accurately. This matters: the judging panel
  includes **Khaled El Emam** (Tier 1 Canada Research Chair in Medical AI; Director,
  OMARI), whose field is health-data de-identification — don't claim "nothing leaves
  the machine" when running the hosted path. Use **synthetic data only** during the
  event — real PHI is governed by **PHIPA** (Ontario) and is out of scope for a
  prototype.

What *not* to build for this room: a generic ambient scribe or a diagnostic
oracle. The clinicians said they want repetitive work removed, not their judgement
replaced.

---

## Quickstart

Works in **mock / deterministic mode** the moment you clone it — no model, no network
required — so the full flow is visible immediately. Verified on Python 3.13 (Windows).

```bash
python -m venv .venv
# Windows:        .venv\Scripts\activate
# macOS / Linux:  source .venv/bin/activate
pip install -r requirements.txt
python run.py                       # -> http://127.0.0.1:8000
```

Three UIs are served:

- **`/office`** — the **Office Assistant** (Direction B MVP): necessity gate → form
  prefill → metrics.
- **`/board`** — the **Patient Context Board** (Direction A): Activity List + 5-card board (snapshot, new/updated, open workflow, limitations, source references).
- **`/`** — the **follow-up extractor**: a note → a structured, reviewable plan.

**Verify the FHIR pipeline offline** (second shell) — this is the integration story:

```bash
curl -X POST localhost:8000/api/fhir/reset
curl -X POST localhost:8000/api/fhir/scan -H 'Content-Type: application/json' -d '{"source":"fixtures","which":1}'
curl -X POST localhost:8000/api/fhir/scan -H 'Content-Type: application/json' -d '{"source":"fixtures","which":2}'
curl localhost:8000/api/fhir/diff      # -> 2 new, 1 updated (metformin 500->1000), 1 not_returned, 7 unchanged
```

For the live `Synthea → local HAPI` path see [`FOUNDATION.md`](FOUNDATION.md).

### Turn on a real model

**Option A — local Ollama (no data egress):**
```bash
# 1. install Ollama:  https://ollama.com/download
# 2. pull a model good at structured extraction:
ollama pull llama3.1            # or: qwen2.5, mistral, gpt-oss
# 3. (re)start the app — it auto-detects Ollama on localhost:11434
python run.py
```

**Option B — OpenRouter (hosted, needs an API key):**
```bash
LLM_PROVIDER=openrouter OPENROUTER_API_KEY=<key> python run.py
```

Now extraction is done by the model and the badge reads **"Drafted by local
model."** (or **"openrouter"** when using Option B). Config via env vars:

| Variable | Default | Notes |
|---|---|---|
| `LLM_PROVIDER` | `ollama` | `openrouter` to route through OpenRouter |
| `OLLAMA_MODEL` | `llama3.1` | Ollama only — try `qwen2.5` / `mistral` |
| `OLLAMA_HOST` | `http://localhost:11434` | Ollama only — point at a remote box if needed |
| `OPENROUTER_API_KEY` | (unset) | OpenRouter only — required |
| `OPENROUTER_MODEL` | `openai/gpt-4o-mini` | OpenRouter only |
| `FORCE_MOCK` | (unset) | set to `1` to demo the UI without any model |

```bash
OLLAMA_MODEL=qwen2.5 python run.py
```

---

## How it works

```
frontend/index.html   Single-file review UI (vanilla JS, no build step).
                      Proposed → Approved/Edited/Removed per item. Evidence
                      snippets + confidence flags. Verified JSON export.

backend/
  schema.py           Pydantic contract the model must fill. One level deep so
                      small local models follow it reliably.
  llm_client.py       Provider router: Ollama (default) or OpenRouter, selected
                      by LLM_PROVIDER. Single call_chat() entry point.
  llm.py              Extraction layer: enforces JSON schema, temperature 0,
                      validate + retry once, mock fallback.
  mock.py             Offline extractor (canned for sample 1, keyword heuristic
                      otherwise) so the UI is demoable with no model installed.
  synthetic_data.py   Three fabricated encounter notes. No real PHI.
  main.py             FastAPI: serves the UI + /api/extract, /api/samples, /api/health.
run.py                Launcher.
```

The reliability trick is **structured outputs**: the Pydantic schema is passed to
Ollama's `format` parameter, the response is validated with
`EncounterExtraction.model_validate_json(...)`, and a failed validation triggers one
corrective retry before falling back to mock. Run the model at `temperature=0` for
stable schema adherence.

---

## Demo script (≈90 seconds)

1. Open on **sample 1** (diabetes + hypertension). One line: *"19 hours a week on
   admin — clinicians told COMPASS they want the repetitive parts gone, not their
   judgement replaced."*
2. **Draft structured follow-up.** Point out it ran **locally** — the note never left
   the laptop.
3. Show the review: med changes, tests, the **referral**, and the *"book the overdue
   foot exam"* task the model surfaced. Flag the **amber low-confidence** item.
4. **Edit one field**, **remove one**, **approve** the rest — make the point that
   *nothing is saved until a human signs off.*
5. **Approve & export** → show the verified JSON with the **audit trail**. *"In a real
   clinic this posts the clinician-approved plan to the EMR. De-identified, local,
   reviewable."*

---

## Where to take it during the day

- **Swap the schema** in `schema.py` for a different COMPASS pain point (referral
  letter drafting, form/sick-note generation, pre-visit summary). The UI renders any
  sections you define — add a section to `SECTIONS` in `index.html`.
- **Wire the export** to a mock EMR endpoint to show the "close the loop" step.
- **Add a pre-visit mode**: feed several past notes → produce a one-screen summary
  before the appointment.
- If a model struggles with the enum fields, relax the `Enum`s in `schema.py` to plain
  `str` and normalize in code — looser schema, easier for tiny models.

---

## Disclaimers

This is a hackathon prototype, **not** a medical device and **not** for clinical use.
Use **synthetic / de-identified data only**. It does not store data, has no auth, and
makes no safety guarantees. Real patient information is governed by PHIPA and your
clinic's policies — keep it out of this tool.
