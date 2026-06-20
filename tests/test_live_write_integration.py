"""
Live FHIR write-back integration test (opt-in, SKIPPED by default).

The live write path -- writer.create POSTing to a real FHIR R4 server and
returning the server-assigned id -- has only ever been verified by hand. This
module codifies it as a repeatable test, but keeps CI and ordinary `pytest`
green with no server by gating the entire module behind an env opt-in.

Run it locally against a HAPI FHIR JPA server:

    docker run -p 8080:8080 hapiproject/hapi:latest        # start a local HAPI

    # PowerShell
    $env:LOOP_LIVE_HAPI = "http://localhost:8080/fhir"
    $env:WRITE_ENABLED  = "1"
    ./.venv/Scripts/python.exe -m pytest tests/test_live_write_integration.py -q

LOOP_LIVE_HAPI carries the FHIR R4 base URL (the only required signal to un-skip).
WRITE_ENABLED=1 is what the writer itself gates on; we assert it here so a half-set
environment fails loudly instead of silently exercising the mock path.

Self-contained and idempotent: each run PUTs its fixtures at deterministic ids so
re-running against the same HAPI overwrites rather than accumulating.
"""

import os
import uuid

import httpx
import pytest

from backend.fhir import action_builder, writer

_BASE_URL = os.environ.get("LOOP_LIVE_HAPI", "").rstrip("/")

pytestmark = pytest.mark.skipif(
    not _BASE_URL,
    reason="set LOOP_LIVE_HAPI=<fhir-base-url> + WRITE_ENABLED=1 and run a local "
    "HAPI to exercise live writes (see module docstring)",
)

# A stable id for this test run's Patient. Stable-per-process (not per-call) so the
# Task/QuestionnaireResponse in this run share one subject; uuid keeps parallel runs
# on a shared HAPI from colliding.
_PATIENT_ID = f"loop-live-test-{uuid.uuid4().hex[:12]}"


def _headers() -> dict[str, str]:
    return {
        "Content-Type": "application/fhir+json",
        "Accept": "application/fhir+json",
    }


@pytest.fixture(scope="module", autouse=True)
def _require_write_enabled() -> None:
    """LOOP_LIVE_HAPI un-skips the module; WRITE_ENABLED is what writer.create gates
    on. If the operator set one but not the other, fail with a clear message rather
    than quietly exercising the mock path and asserting against simulated ids."""
    if writer._write_enabled():  # noqa: SLF001 -- exercising the writer's own gate
        return
    pytest.fail(
        "LOOP_LIVE_HAPI is set but WRITE_ENABLED is not truthy; the writer would "
        "fall back to the mock path. Set WRITE_ENABLED=1 to run live writes."
    )


@pytest.fixture(scope="module")
def patient_id() -> str:
    """PUT a Patient at a known id into the HAPI base so Task.for / QR.subject
    references resolve. PUT (update-or-create) makes this idempotent."""
    resource = {
        "resourceType": "Patient",
        "id": _PATIENT_ID,
        "name": [{"family": "LoopLiveTest", "given": ["Integration"]}],
        "gender": "unknown",
    }
    r = httpx.put(
        f"{_BASE_URL}/Patient/{_PATIENT_ID}",
        json=resource,
        headers=_headers(),
        timeout=30,
    )
    r.raise_for_status()
    return _PATIENT_ID


def _get(rtype: str, rid: str) -> httpx.Response:
    return httpx.get(f"{_BASE_URL}/{rtype}/{rid}", headers=_headers(), timeout=30)


def test_writer_creates_task_live(patient_id: str) -> None:
    resource = action_builder.build_task(
        patient_id, "Live-write integration: follow-up labs in 2 weeks"
    )

    result = writer.create(resource, base_url=_BASE_URL)

    assert result["mode"] == "written", result
    assert result["resourceType"] == "Task"
    rid = result["id"]
    assert rid, f"expected a server-assigned id, got {result!r}"

    got = _get("Task", rid)
    assert got.status_code == 200, got.text
    body = got.json()
    assert body["resourceType"] == "Task"
    assert body["id"] == rid
    assert body["for"]["reference"] == f"Patient/{patient_id}"


def test_writer_creates_questionnaire_response_live(patient_id: str) -> None:
    # questionnaire is a canonical (absolute) URL, so HAPI accepts the write without
    # hosting the Questionnaire itself -- the case that used to require manual checking.
    resource = action_builder.build_questionnaire_response(
        patient_id,
        "phq9",
        [{"linkId": "q1", "text": "Little interest or pleasure", "value": "Several days"}],
    )

    result = writer.create(resource, base_url=_BASE_URL)

    assert result["mode"] == "written", result
    assert result["resourceType"] == "QuestionnaireResponse"
    rid = result["id"]
    assert rid, f"expected a server-assigned id, got {result!r}"

    got = _get("QuestionnaireResponse", rid)
    assert got.status_code == 200, got.text
    body = got.json()
    assert body["resourceType"] == "QuestionnaireResponse"
    assert body["id"] == rid
    assert body["subject"]["reference"] == f"Patient/{patient_id}"
    assert body["questionnaire"].startswith("http")
