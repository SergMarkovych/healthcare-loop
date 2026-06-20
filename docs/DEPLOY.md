# Deploy — run on another machine (Docker)

The whole app ships as one container. **Synthetic data only; no PHI; runs fully offline**
(no model, no network) by default. The only prerequisite on the target PC is **Docker**
(Docker Desktop on Windows/macOS, or Docker Engine on Linux).

## Quick start (offline, recommended)

```bash
git clone https://github.com/SergMarkovych/healthcare-loop.git
cd healthcare-loop
docker compose up --build
```

Then open:
- **http://localhost:8000/board** — Patient Context Board (pre-visit, source-backed)
- **http://localhost:8000/office** — Office Assistant (paperwork triage + form prefill)

Load the demo data from the board's **"Load synthetic scans"** button (fixtures, offline),
then open a patient. Everything is deterministic — no model or network required.

Stop with `Ctrl+C`, or `docker compose down`.

### Without compose (single container)

```bash
docker build -t healthcare-loop .
docker run --rm -p 8000:8000 healthcare-loop
```

## Live FHIR mode (optional — real scan/diff)

Starts a local **HAPI FHIR** server alongside the app:

```bash
docker compose --profile live up --build
```

Then load synthetic patients into HAPI and point the app at it:
1. `bash scripts/load_local_hapi.sh` (loads the bundled synthetic patients into `:8080`), or
   POST your own FHIR transaction bundle to `http://localhost:8080/fhir`.
2. Set `FHIR_BASE_URL=http://hapi:8080/fhir` for the `app` service (uncomment it in
   `docker-compose.yml`) and re-up, **or** call the API directly:
   `POST /api/fhir/scan {"source":"live","base_url":"http://localhost:8080/fhir","patient_count":15}`.

See [`live-fhir-demo.md`](live-fhir-demo.md) for the controlled-change diff walkthrough.

## Configuration (environment variables)

| Var | Default (container) | Purpose |
|---|---|---|
| `FORCE_MOCK` | `1` | Office extractor uses the deterministic mock (no Ollama). |
| `FORCE_DETERMINISTIC` | `1` | Board summary stays deterministic/offline. |
| `FHIR_BASE_URL` | `https://hapi.fhir.org/baseR4` | FHIR server for `source=live` scans. |
| `LLM_PROVIDER` | `ollama` | Set to `openrouter` to use OpenRouter instead of Ollama. |
| `OLLAMA_HOST` / `OLLAMA_MODEL` | `localhost:11434` / `llama3.1` | Ollama only — unset the mock flags first. |
| `OPENROUTER_API_KEY` | (unset) | OpenRouter only — required when `LLM_PROVIDER=openrouter`. |
| `OPENROUTER_MODEL` | `openai/gpt-4o-mini` | OpenRouter only — model slug from openrouter.ai. |

## Ports
- **8000** — the app (board / office / API).
- **8080** — HAPI FHIR (only with `--profile live`).

## Notes
- Health check: `GET /api/health` (the container's Docker healthcheck uses it).
- The SQLite snapshot store lives inside the container and is ephemeral; that's intended
  for a demo. For persistence, mount a volume at `/app/backend/fhir/`.
- Not a medical device; synthetic/de-identified data only (PHIPA governs real data).
