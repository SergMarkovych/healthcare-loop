"""
FastAPI backend. Serves the single-file frontend and three JSON endpoints.

Run from the repo root:
    python run.py
    # or: uvicorn backend.main:app --reload --port 8000
Then open http://127.0.0.1:8000
"""

from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from pydantic import BaseModel

from backend import llm
from backend.fhir import service as fhir_service
from backend.office import service as office_service
from backend.synthetic_data import SAMPLES

app = FastAPI(title="Loop — follow-up co-pilot (scaffold)")

_FRONTEND = Path(__file__).resolve().parent.parent / "frontend" / "index.html"


class ExtractRequest(BaseModel):
    note: str
    sample_id: str | None = None


@app.get("/", response_class=HTMLResponse)
def index() -> str:
    return _FRONTEND.read_text(encoding="utf-8")


@app.get("/office", response_class=HTMLResponse)
def office_ui() -> str:
    return (_FRONTEND.parent / "office.html").read_text(encoding="utf-8")


@app.get("/api/health")
def health() -> dict:
    return {
        "status": "ok",
        "model": llm.OLLAMA_MODEL,
        "host": llm.OLLAMA_HOST,
        "force_mock": llm.FORCE_MOCK,
    }


@app.get("/api/samples")
def samples() -> list[dict]:
    return [{"id": s["id"], "title": s["title"], "note": s["note"]} for s in SAMPLES]


@app.post("/api/extract")
def extract(req: ExtractRequest) -> dict:
    extraction, mode = llm.extract(req.note, req.sample_id)
    return {"mode": mode, "extraction": extraction.model_dump()}


# --- FHIR Patient Context Board foundation (shared substrate) ---

class ScanRequest(BaseModel):
    source: str = "fixtures"        # 'fixtures' (offline) | 'live' (FHIR base URL)
    which: int | None = None        # fixtures only: 1 or 2
    base_url: str | None = None     # live only: override FHIR base URL
    patient_count: int = 5


@app.get("/api/fhir/health")
def fhir_health() -> dict:
    return {"status": "ok", "fhir_base_url": fhir_service.FHIR_BASE_URL}


@app.post("/api/fhir/scan")
def fhir_scan(req: ScanRequest) -> dict:
    return fhir_service.run_scan(
        source=req.source, which=req.which,
        base_url=req.base_url, patient_count=req.patient_count,
    )


@app.get("/api/fhir/diff")
def fhir_diff() -> dict:
    return fhir_service.diff_last_two()


@app.get("/api/fhir/patients")
def fhir_patients() -> list[dict]:
    return fhir_service.list_patients_latest()


@app.get("/api/fhir/context/{patient_id}")
def fhir_context(patient_id: str) -> dict:
    return fhir_service.build_context(patient_id)


@app.post("/api/fhir/reset")
def fhir_reset() -> dict:
    fhir_service.reset_store()
    return {"status": "reset"}


# --- Digital medical office assistant (challenge area #5) ---

class PrefillRequest(BaseModel):
    request_id: str


class MetricsRequest(BaseModel):
    processed: list[dict] = []


@app.get("/api/office/requests")
def office_requests() -> list[dict]:
    return office_service.get_queue()


@app.post("/api/office/prefill")
def office_prefill(req: PrefillRequest) -> dict:
    return office_service.prefill_request(req.request_id)


@app.post("/api/office/metrics")
def office_metrics(req: MetricsRequest) -> dict:
    return office_service.project(req.processed)
