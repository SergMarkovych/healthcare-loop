"""
Safe context summary.

Hard rule (this is the whole safety story): the summary may ONLY restate
API-backed data/workflow activity. It must never diagnose, prescribe, recommend
treatment, or interpret whether a value is good/bad. Two defences:

  1. The deterministic builder composes the board from the structured diff only —
     it literally cannot invent clinical content.
  2. If a local LLM is used to phrase the prose, its output is run through a
     post-filter; any forbidden wording => discard the LLM text, fall back to
     deterministic. Fail safe, not fail open.

Returns (board: dict, mode: 'deterministic' | 'local-model').
"""

import json
import os

# Wording that implies clinical judgement. If the model emits any of these, we
# throw its text away and use the deterministic summary instead.
_FORBIDDEN = [
    "diagnos", "prescrib", "uncontrolled", "should order", "order labs",
    "change medication", "stop medication", "start medication", "recommend",
    "treatment", "risk score", "abnormal", "is normal", "elevated",
    "too high", "too low", "concerning", "needs ", "worsening", "improving",
]

OLLAMA_HOST = os.environ.get("OLLAMA_HOST", "http://localhost:11434")
OLLAMA_MODEL = os.environ.get("OLLAMA_MODEL", "llama3.1")
FORCE_DETERMINISTIC = os.environ.get("FORCE_DETERMINISTIC", "").lower() in ("1", "true", "yes")

_WORKFLOW_OPEN = {"active", "requested", "in-progress", "on-hold", "received", "accepted"}


def _display_name(patient: dict | None) -> str:
    if not patient:
        return "Unknown patient"
    names = patient.get("name") or []
    if names:
        n = names[0]
        given = " ".join(n.get("given", []))
        return f"{given} {n.get('family', '')}".strip() or patient.get("id", "Unknown")
    return patient.get("id", "Unknown")


def build_board(patient_id, patient_resource, pdiff, current_resources, requested_types):
    """Compose the neutral, source-backed board structure from the diff only."""
    present_types = {r.get("resourceType") for r in current_resources}
    not_returned_types = sorted(t for t in requested_types if t not in present_types)

    open_items = []
    for r in current_resources:
        rt = r.get("resourceType")
        status = (r.get("status") or "").lower()
        if rt in ("Task", "ServiceRequest") and status in _WORKFLOW_OPEN:
            label = (
                (r.get("code", {}) or {}).get("text")
                or (r.get("description"))
                or f"{rt}/{r.get('id')}"
            )
            open_items.append({"resource": f"{rt}/{r.get('id')}", "status": status, "label": label})

    source_refs = sorted({i["key"] for grp in ("new", "updated", "not_returned")
                          for i in pdiff.get(grp, [])})

    return {
        "patient_id": patient_id,
        "snapshot": {
            "name": _display_name(patient_resource),
            "gender": (patient_resource or {}).get("gender"),
            "birthDate": (patient_resource or {}).get("birthDate"),
        },
        "changes": {
            "new": pdiff.get("new", []),
            "updated": pdiff.get("updated", []),
            "not_returned": pdiff.get("not_returned", []),
            "counts": pdiff.get("counts", {}),
        },
        "open_workflow_items": open_items,
        "data_source_limitations": (
            [f"{t} not returned by current API response." for t in not_returned_types]
            or ["All requested resource types were returned by the API."]
        ),
        "source_references": source_refs,
    }


def deterministic_text(board: dict) -> str:
    c = board["changes"]["counts"]
    s = board["snapshot"]
    lines = [
        f"Patient context for {s['name']} "
        f"({s.get('gender') or 'sex n/a'}, born {s.get('birthDate') or 'DOB n/a'}), "
        f"assembled from the FHIR API.",
        f"Since the previous scan: {c.get('new', 0)} new, {c.get('updated', 0)} updated, "
        f"{c.get('not_returned', 0)} not returned.",
    ]
    for it in board["changes"]["new"]:
        lines.append(f"New {it['resource_type']} returned ({it['key']}).")
    for it in board["changes"]["updated"]:
        lines.append(f"{it['resource_type']} updated ({it['key']}): "
                     f"{it.get('change_count', 0)} field change(s).")
    for it in board["changes"]["not_returned"]:
        lines.append(f"{it['resource_type']} not returned by current API response ({it['key']}).")
    for w in board["open_workflow_items"]:
        lines.append(f"Open workflow item: {w['label']} (status: {w['status']}).")
    return "\n".join(lines)


def _passes_safety(text: str) -> bool:
    low = text.lower()
    return not any(term in low for term in _FORBIDDEN)


def _llm_text(board: dict) -> str | None:
    """Optional: let a local model phrase the same facts. Returns None on any issue."""
    try:
        from ollama import Client
    except ImportError:
        return None
    prompt = (
        "You are a chart-context summarization assistant. You are NOT a doctor. "
        "Do not diagnose, prescribe, recommend treatment, or say whether any value is "
        "good or bad. Do not infer facts that are not in the data below. Only restate, "
        "in neutral language, the data/workflow changes provided as JSON.\n\n"
        f"{json.dumps(board, ensure_ascii=False)}"
    )
    try:
        client = Client(host=OLLAMA_HOST, timeout=60)
        resp = client.chat(
            model=OLLAMA_MODEL,
            messages=[{"role": "user", "content": prompt}],
            options={"temperature": 0},
        )
        return resp["message"]["content"]
    except Exception as err:
        print(f"[fhir.summarize] local model unavailable ({err}); deterministic.")
        return None


def summarize(patient_id, patient_resource, pdiff, current_resources, requested_types):
    board = build_board(patient_id, patient_resource, pdiff, current_resources, requested_types)
    det = deterministic_text(board)

    if not FORCE_DETERMINISTIC:
        text = _llm_text(board)
        if text and _passes_safety(text):
            board["summary_text"] = text.strip()
            return board, "local-model"

    board["summary_text"] = det
    return board, "deterministic"
