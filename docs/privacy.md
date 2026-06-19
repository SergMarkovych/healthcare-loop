# Privacy & safety one-pager

A prototype for the COMPASS *AI in Healthcare* program. Designed privacy-first because
the judging panel includes a medical-AI de-identification expert — the privacy story has
to be precise, not hand-wavy.

## Data
- **Synthetic data only.** Every patient, request, and FHIR resource in this build is
  fabricated. **No real PHI, ever.** Real patient information is governed by **PHIPA**
  (Ontario) and is out of scope for a prototype.
- **No persistence of clinical content beyond the local snapshot store.** The only store
  is a local SQLite file of FHIR snapshots used for change detection; it holds synthetic
  data and is git-ignored.

## Processing
- **Local-first.** The app runs on a laptop. When a local model (Ollama) is used it runs
  on `localhost`; **no encounter text or patient data leaves the machine**.
- **Deterministic fallback.** With no model and no network the app runs fully in
  mock/deterministic mode — so locality is the default, not a configuration.

## What the AI may and may not do
- **It restates source-backed facts only.** Summaries and prefilled fields are derived
  from FHIR-API data or workflow activity, each carrying **evidence + a confidence flag**.
- **It invents nothing clinical.** Fields that require clinical judgement — functional
  limitations, onset, prognosis, work capacity — are **flagged for the physician and left
  blank**, never guessed.
- **It does not diagnose, prescribe, or interpret values.** A safety post-filter discards
  any model text that drifts into clinical-decision wording and substitutes the
  deterministic summary. *Fail safe.*

## Human control
- **The physician approves every clinical output.** Nothing is committed automatically;
  each suggestion is a proposal to approve, edit, or remove, with an audit trail.

## Boundaries
This is a **hackathon prototype, not a medical device** and not for clinical use. It has
no authentication and makes no safety guarantees. Keep real patient information out of it.
