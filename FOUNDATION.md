# Foundation (today's prep) — FHIR-backed · snapshot-capable · source-safe

This layer is the **fork-independent substrate** both finalist concepts need, so
today's hours pay off no matter which you commit to tomorrow:

- **Patient Context Board** (continuity / "what changed since last visit") — uses
  the scan → snapshot → diff → safe-summary pipeline directly.
- **Form / necessity-gate tool** (paperwork) — uses the FHIR client to pull *real*
  API-backed patient data into the extractor, and the "AI only restates
  source-backed facts" discipline.

It also retires the single most dangerous assumption from the foresight:
**does local AI behave on real FHIR data?** You answer that today, offline first.

Safety posture baked in: synthetic/test data only, summaries restate only
API-backed data/workflow activity (never diagnose/prescribe/interpret), a
post-filter discards any model text that slips into clinical wording, and a
deterministic fallback means the demo never dead-ends. Real PHI is out of scope
(PHIPA).

---

## 1. Run it offline right now (no network, no server)

```bash
pip install -r requirements.txt
python run.py                      # http://127.0.0.1:8000

# in a second shell — the whole pipeline on synthetic fixtures:
curl -X POST localhost:8000/api/fhir/reset
curl -X POST localhost:8000/api/fhir/scan -H 'Content-Type: application/json' -d '{"source":"fixtures","which":1}'
curl -X POST localhost:8000/api/fhir/scan -H 'Content-Type: application/json' -d '{"source":"fixtures","which":2}'
curl localhost:8000/api/fhir/diff
curl localhost:8000/api/fhir/context/synthetic-A
```

What you'll see: between scan 1 and 2 the engine reports **2 new** (a Creatinine
Observation, a Task), **1 updated** (Metformin dose 500 → 1000, with the exact
field-level change), **1 not returned** (a prior BP Observation), and **7
unchanged** — including an A1c whose `lastUpdated` was bumped but content was
identical, proving change detection is content-hash based, not metadata based.
Patient B's board surfaces the open Task as a workflow item.

## 2. Endpoints

| Endpoint | Purpose |
|---|---|
| `POST /api/fhir/scan` | Run a scan. Body: `{"source":"fixtures","which":1|2}` or `{"source":"live","patient_count":5,"base_url":"…"}` |
| `GET  /api/fhir/diff` | Classify changes between the last two scans |
| `GET  /api/fhir/patients` | Patients in the latest scan |
| `GET  /api/fhir/context/{id}` | Safe, source-backed context board for one patient |
| `POST /api/fhir/reset` | Clear the snapshot store (handy between demo runs) |

The existing form tool (`/api/extract`, `/api/samples`) is untouched.

## 3. Go live with real FHIR data

**Fast path — public HAPI** (good for proving the API flow; updates between scans
aren't guaranteed):

```bash
export FHIR_BASE_URL=https://hapi.fhir.org/baseR4
curl -X POST localhost:8000/api/fhir/scan -H 'Content-Type: application/json' -d '{"source":"live","patient_count":5}'
```

**Controlled path — Synthea → local HAPI** (best demo: you control the change):

```bash
# 1. local FHIR server
docker run -d --name hapi -p 8080:8080 hapiproject/hapi:latest      # base: http://localhost:8080/fhir

# 2. synthetic patients
git clone https://github.com/synthetichealth/synthea && cd synthea
./run_synthea -p 8                                                  # -> output/fhir/*.json (transaction bundles)

# 3. load them
for f in output/fhir/*.json; do
  curl -s -X POST http://localhost:8080/fhir \
       -H 'Content-Type: application/fhir+json' --data-binary @"$f" > /dev/null
done

# 4. point the app at it
export FHIR_BASE_URL=http://localhost:8080/fhir
```

Demo the diff: scan live (= scan 1) → update one resource through the API (e.g.
`PUT http://localhost:8080/fhir/MedicationRequest/{id}` with a changed dose) →
scan live again (= scan 2) → `GET /api/fhir/diff`.

## 4. Turn on the local-model summary (optional)

The board prose is deterministic by default (safe + offline). To let a local
model phrase it instead:

```bash
# install Ollama: https://ollama.com/download
ollama pull llama3.1                 # or qwen2.5 / mistral
unset FORCE_DETERMINISTIC            # allow the model; output still passes the safety filter
```

If the model emits any clinical-decision wording, its text is discarded and the
deterministic summary is used. Fail safe.

---

## 5. Today's 5+ hours — parallel checklist

While the foundation is in place, spend today proving and prepping:

- [ ] Run the offline fixtures demo end-to-end (section 1) — confirm the diff story reads well.
- [ ] `ollama pull` a model and run a few extractions/summaries — **judge the real quality** (this is the assumption test).
- [ ] Stand up Synthea → local HAPI (section 3) so tomorrow's demo has controllable changes.
- [ ] Pick the candidate **form** for the form-path (sick note to *eliminate*, DTC to *prefill*) and sketch its fields → which are clinical (physician) vs admin (auto) vs delegable.
- [ ] Draft the privacy one-pager ("data never leaves the machine" + PHIPA) and the 90-second demo script.
- [ ] Write the discovery questions for the 9:30 physician panel.

## 6. Tomorrow's cheap fork (decide after the 9:30 panel)

Confirm the COMPASS challenge area first, then branch — the substrate is shared:

- **Continuity / pre-visit prep / "what changed"** → **Patient Context Board.** Add a
  board UI on top of `GET /api/fhir/context/{id}` and the patient activity list on
  `GET /api/fhir/diff`. Backend is done; this is a UI day.
- **Paperwork / forms burden** → **form / necessity-gate tool.** Feed the FHIR context
  into Loop's extractor → prefill one form, mark fields `eliminate / delegate /
  automate / physician-review`, show the saved-minutes panel. Now backed by *real*
  FHIR data instead of pasted text.
- **Hybrid (if time):** "what changed → which form/task that triggers → prefill →
  necessity-gate → minutes saved." Both halves on one substrate.

Either way, the lean local stack holds and the mock/deterministic fallbacks keep
the demo bulletproof.
