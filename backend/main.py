"""
FastAPI backend. Serves the single-file frontend and three JSON endpoints.

Run from the repo root:
    python run.py
    # or: uvicorn backend.main:app --reload --port 8000
Then open http://127.0.0.1:8000
"""

from pathlib import Path
from typing import Literal

from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from pydantic import BaseModel

from backend import llm
from backend.board import service as board_service
from backend.fhir import action_builder
from backend.fhir import service as fhir_service
from backend.fhir import sources as fhir_sources
from backend.fhir import writer as fhir_writer
from backend.office import service as office_service
from backend.office import summarizer as office_summarizer
from backend.office import verifier as office_verifier
from backend.synthetic_data import SAMPLES
from backend.transcribe import router as transcribe_router

app = FastAPI(title="Loop — follow-up co-pilot (scaffold)")
app.include_router(transcribe_router)

_FRONTEND = Path(__file__).resolve().parent.parent / "frontend" / "index.html"


class ExtractRequest(BaseModel):
    note: str
    sample_id: str | None = None


class ProviderConfig(BaseModel):
    provider: Literal["mock", "ollama", "openrouter"]


@app.get("/", response_class=HTMLResponse)
def index() -> str:
    return _FRONTEND.read_text(encoding="utf-8")


@app.get("/office", response_class=HTMLResponse)
def office_ui() -> str:
    return (_FRONTEND.parent / "office.html").read_text(encoding="utf-8")


@app.get("/board", response_class=HTMLResponse)
def board_ui() -> str:
    return (_FRONTEND.parent / "board.html").read_text(encoding="utf-8")


@app.get("/api/health")
def health() -> dict:
    from backend import llm_client
    return {
        "status": "ok",
        "provider": llm_client.LLM_PROVIDER,
        "model": llm_client.OPENROUTER_MODEL if llm_client.LLM_PROVIDER == "openrouter" else llm_client.OLLAMA_MODEL,
        "host": "https://openrouter.ai/api/v1" if llm_client.LLM_PROVIDER == "openrouter" else llm_client.OLLAMA_HOST,
        "force_mock": llm.FORCE_MOCK,
    }


@app.get("/api/probe")
def probe() -> dict:
    from backend import llm_client
    import httpx
    if llm.FORCE_MOCK:
        return {"ok": True, "provider": "mock"}
    if llm_client.LLM_PROVIDER == "openrouter":
        try:
            r = httpx.post(
                "https://openrouter.ai/api/v1/chat/completions",
                headers={"Authorization": f"Bearer {llm_client.OPENROUTER_API_KEY}",
                         "Content-Type": "application/json"},
                json={"model": llm_client.OPENROUTER_MODEL,
                      "messages": [{"role": "user", "content": "hi"}],
                      "max_tokens": 1},
                timeout=8,
            )
            return {"ok": r.status_code == 200, "provider": "openrouter"}
        except Exception as e:
            return {"ok": False, "provider": "openrouter", "error": str(e)}
    if llm_client.LLM_PROVIDER == "ollama":
        try:
            r = httpx.get(f"{llm_client.OLLAMA_HOST}/api/tags", timeout=3)
            return {"ok": r.status_code == 200, "provider": "ollama"}
        except Exception as e:
            return {"ok": False, "provider": "ollama", "error": str(e)}
    return {"ok": False, "provider": "unknown"}


@app.post("/api/config")
def set_config(req: ProviderConfig) -> dict:
    from backend import llm_client
    from backend.fhir import summarize as fhir_summarize
    if req.provider == "mock":
        llm.FORCE_MOCK = True
        fhir_summarize.FORCE_DETERMINISTIC = True
    else:
        llm.FORCE_MOCK = False
        fhir_summarize.FORCE_DETERMINISTIC = False
        llm_client.LLM_PROVIDER = req.provider
    return health()


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


@app.get("/api/fhir/activity")
def fhir_activity() -> list[dict]:
    return fhir_service.patient_activity()


@app.get("/api/sources")
def sources() -> list[dict]:
    return fhir_sources.load_sources()


@app.get("/api/fhir/context/{patient_id}")
def fhir_context(patient_id: str) -> dict:
    return fhir_service.build_context(patient_id)


@app.post("/api/fhir/reset")
def fhir_reset() -> dict:
    fhir_service.reset_store()
    return {"status": "reset"}


@app.get("/api/board/{patient_id}")
def board(patient_id: str) -> dict:
    return board_service.get_board(patient_id)


# --- Digital medical office assistant (challenge area #5) ---

class PrefillRequest(BaseModel):
    request_id: str


class ApproveRequest(BaseModel):
    request_id: str
    completed_fields: dict[str, str] = {}


class MetricsRequest(BaseModel):
    processed: list[dict] = []


class SummarizeRequest(BaseModel):
    text: str


@app.get("/api/office/requests")
def office_requests() -> list[dict]:
    return office_service.get_queue()


@app.post("/api/office/prefill")
def office_prefill(req: PrefillRequest) -> dict:
    return office_service.prefill_request(req.request_id)


@app.post("/api/office/approve")
def office_approve(req: ApproveRequest) -> dict:
    return office_service.approve_request(req.request_id, req.completed_fields)


@app.post("/api/office/metrics")
def office_metrics(req: MetricsRequest) -> dict:
    return office_service.project(req.processed)


@app.get("/api/office/handout/{request_id}")
def office_handout(request_id: str) -> dict:
    return office_service.build_handout_for(request_id)


@app.post("/api/office/verify")
def office_verify(req: office_verifier.VerifyRequest) -> office_verifier.VerifyResult:
    return office_verifier.verify(req)


@app.post("/api/office/summarize")
def office_summarize(req: SummarizeRequest) -> office_summarizer.OfficeSummary:
    return office_summarizer.summarize(req.text)


# --- Actions: close the loop by writing the approved item back to FHIR ---
# These represent the physician's approval. By default (WRITE_ENABLED unset) they
# simulate the write and return a synthetic id; with WRITE_ENABLED truthy and a
# FHIR_BASE_URL pointed at a local HAPI they perform a real POST.

class ActionRequest(BaseModel):
    kind: str                       # task | service_request | communication_request | questionnaire_response
    patient_id: str
    payload: dict = {}
    base_url: str | None = None
    if_none_exist: str | None = None


class BatchActionRequest(BaseModel):
    actions: list[ActionRequest] = []
    base_url: str | None = None


@app.post("/api/fhir/action")
def fhir_action(req: ActionRequest) -> dict:
    try:
        resource = action_builder.build(req.kind, req.patient_id, req.payload)
    except ValueError as e:
        return {"status": "error", "reason": str(e)}
    result = fhir_writer.create(resource, base_url=req.base_url, if_none_exist=req.if_none_exist)
    return {"kind": req.kind, "mode": result.get("mode"),
            "resource": result.get("resource", resource), "result": result}


@app.post("/api/fhir/action/batch")
def fhir_action_batch(req: BatchActionRequest) -> dict:
    resources = []
    for a in req.actions:
        try:
            resources.append(action_builder.build(a.kind, a.patient_id, a.payload))
        except ValueError as e:
            return {"status": "error", "reason": str(e)}
    bundle = action_builder.build_transaction_bundle(resources)
    result = fhir_writer.transaction(bundle, base_url=req.base_url)
    return {"count": len(resources), "mode": result.get("mode"), "result": result}
