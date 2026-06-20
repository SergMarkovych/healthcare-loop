"""
FHIR Writer — perform the approved action by writing a resource via the FHIR API.

Two modes:
  - written: POST to the FHIR R4 base URL (use a LOCAL HAPI for writes, never the
    public test server). Returns the server-assigned id.
  - mock: the default. Simulate the create and return a synthetic id so the demo
    always completes with no network.

Gating (safe by default, the inverse of the read side):
  - Writes are MOCK unless WRITE_ENABLED is truthy. Absence of the flag = mock.
    This is deliberate: a write mutates an EMR, so nothing leaves the process
    until an operator explicitly opts in (WRITE_ENABLED=1 + FHIR_BASE_URL set).
  - These functions represent the physician's approval — callers invoke them only
    after the physician approves the drafted resource.

FHIR_BASE_URL is sourced from backend.fhir.service so reads and writes share one
configured base URL (loop convention).
"""

import os

import httpx

from backend.fhir.service import FHIR_BASE_URL

_TRUTHY = {"1", "true", "yes", "on"}

# Per-process counter for deterministic-shaped mock ids (mock-<type>-<n>).
_mock_seq = 0


def _write_enabled() -> bool:
    return os.environ.get("WRITE_ENABLED", "").strip().lower() in _TRUTHY


def _base_url(base_url: str | None) -> str:
    if base_url:
        return base_url.rstrip("/")
    # An explicitly-set env var wins even when empty (a way to disable live writes);
    # only when FHIR_BASE_URL is absent from the env do we fall back to the
    # service-configured default.
    env = os.environ.get("FHIR_BASE_URL")
    base = env if env is not None else FHIR_BASE_URL
    return (base or "").rstrip("/")


def _next_seq() -> int:
    global _mock_seq
    _mock_seq += 1
    return _mock_seq


def _mock_id(rtype: str) -> str:
    return f"mock-{rtype.lower()}-{_next_seq()}"


def _mock_create(resource: dict) -> dict:
    rtype = resource.get("resourceType", "Resource")
    rid = _mock_id(rtype)
    return {
        "status": "created", "mode": "mock", "id": rid,
        "resourceType": rtype, "location": f"{rtype}/{rid}",
        "resource": {**resource, "id": rid},
        "note": "Simulated write (WRITE_ENABLED off or no live server). "
                "On a local HAPI with WRITE_ENABLED set this is a real POST.",
    }


def create(resource: dict, *, base_url: str | None = None,
           if_none_exist: str | None = None) -> dict:
    rtype = resource.get("resourceType")
    if not rtype:
        return {"status": "error", "reason": "resource has no resourceType"}

    base = _base_url(base_url)
    if not _write_enabled() or not base:
        return _mock_create(resource)

    headers = {"Content-Type": "application/fhir+json", "Accept": "application/fhir+json"}
    if if_none_exist:
        headers["If-None-Exist"] = if_none_exist
    try:
        r = httpx.post(f"{base}/{rtype}", json=resource, headers=headers, timeout=30)
        r.raise_for_status()
        body = r.json() if r.content else {}
        rid = body.get("id") or r.headers.get("Location", "").rstrip("/").split("/")[-1]
        return {"status": "created", "mode": "written", "id": rid,
                "resourceType": rtype,
                "location": r.headers.get("Location", f"{rtype}/{rid}"),
                "resource": body or resource}
    except httpx.HTTPError as err:
        # Never fail the demo: fall back to a simulated create and say so.
        out = _mock_create(resource)
        out["note"] = f"Live write to {base} failed ({err}); returned a simulated create instead."
        return out


def transaction(bundle: dict, *, base_url: str | None = None) -> dict:
    entries = bundle.get("entry", [])
    base = _base_url(base_url)
    if not _write_enabled() or not base:
        created = [_mock_create(e["resource"])["location"] for e in entries if "resource" in e]
        return {"status": "created", "mode": "mock", "count": len(created),
                "locations": created,
                "note": "Simulated transaction (WRITE_ENABLED off or no live server). "
                        "On a local HAPI this POSTs the Bundle atomically."}

    headers = {"Content-Type": "application/fhir+json", "Accept": "application/fhir+json"}
    try:
        r = httpx.post(base, json=bundle, headers=headers, timeout=60)
        r.raise_for_status()
        return {"status": "created", "mode": "written",
                "response": r.json() if r.content else {}}
    except httpx.HTTPError as err:
        created = [_mock_create(e["resource"])["location"] for e in entries if "resource" in e]
        return {"status": "created", "mode": "mock", "count": len(created),
                "locations": created,
                "note": f"Live transaction to {base} failed ({err}); simulated instead."}
