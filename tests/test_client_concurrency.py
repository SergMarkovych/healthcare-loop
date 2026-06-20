"""
Concurrency + content-equivalence tests for FHIRClient.scan().

scan() fans patients out over a bounded ThreadPoolExecutor while reusing the
shared httpx.Client. These tests stub the network with httpx.MockTransport so
nothing touches a real server, and verify:

  (a) scan() returns every expected resource for N patients,
  (b) a per-type fetch error is captured in `errors`, not raised,
  (c) the work is actually concurrent (overlapping in-flight calls + wall-time
      far below the sequential lower bound when each call sleeps).
"""

import threading
import time

import httpx
import pytest

from backend.fhir.client import FHIRClient

TYPES = ["Condition", "Observation"]


def _bundle(resources: list[dict]) -> dict:
    return {
        "resourceType": "Bundle",
        "type": "searchset",
        "entry": [{"resource": r} for r in resources],
    }


def _make_client(handler, base_url: str = "https://fhir.example/r4") -> FHIRClient:
    """Build a FHIRClient whose internal httpx.Client is driven by `handler`."""
    fc = FHIRClient(base_url)
    fc._client = httpx.Client(
        base_url=base_url,
        transport=httpx.MockTransport(handler),
        headers={"Accept": "application/fhir+json"},
    )
    return fc


def _patient_search_response(patient_ids: list[str]) -> httpx.Response:
    patients = [{"resourceType": "Patient", "id": pid} for pid in patient_ids]
    return httpx.Response(200, json=_bundle(patients))


def test_scan_returns_all_resources_for_n_patients():
    patient_ids = [f"p{i}" for i in range(6)]

    def handler(request: httpx.Request) -> httpx.Response:
        path = request.url.path
        if path.endswith("/Patient"):
            return _patient_search_response(patient_ids)
        rtype = path.rsplit("/", 1)[-1]
        pid = request.url.params.get("patient")
        res = {"resourceType": rtype, "id": f"{rtype}-{pid}", "subject": {"reference": f"Patient/{pid}"}}
        return httpx.Response(200, json=_bundle([res]))

    fc = _make_client(handler)
    try:
        resources, errors = fc.scan(patient_count=len(patient_ids), types=TYPES)
    finally:
        fc.close()

    assert errors == []
    patients = [r for r in resources if r["resourceType"] == "Patient"]
    assert {p["id"] for p in patients} == set(patient_ids)
    # one Patient + one resource per type, per patient
    assert len(resources) == len(patient_ids) * (1 + len(TYPES))
    for pid in patient_ids:
        for rtype in TYPES:
            assert any(
                r["resourceType"] == rtype and r["id"] == f"{rtype}-{pid}"
                for r in resources
            )


def test_per_type_fetch_error_is_captured_not_raised():
    patient_ids = ["p0", "p1"]

    def handler(request: httpx.Request) -> httpx.Response:
        path = request.url.path
        if path.endswith("/Patient"):
            return _patient_search_response(patient_ids)
        rtype = path.rsplit("/", 1)[-1]
        pid = request.url.params.get("patient")
        if rtype == "Observation" and pid == "p1":
            return httpx.Response(500, json={"resourceType": "OperationOutcome"})
        res = {"resourceType": rtype, "id": f"{rtype}-{pid}"}
        return httpx.Response(200, json=_bundle([res]))

    fc = _make_client(handler)
    try:
        resources, errors = fc.scan(patient_count=len(patient_ids), types=TYPES)
    finally:
        fc.close()

    assert len(errors) == 1
    err = errors[0]
    assert err["resource_type"] == "Observation"
    assert err["patient_id"] == "p1"
    assert "error" in err
    # the failed (type, patient) is absent; everything else is present
    assert not any(r.get("id") == "Observation-p1" for r in resources)
    assert any(r.get("id") == "Observation-p0" for r in resources)
    assert any(r.get("id") == "Condition-p1" for r in resources)


def test_scan_is_actually_concurrent():
    patient_ids = [f"p{i}" for i in range(8)]
    sleep_per_call = 0.05

    in_flight = 0
    max_in_flight = 0
    lock = threading.Lock()

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal in_flight, max_in_flight
        if request.url.path.endswith("/Patient"):
            return _patient_search_response(patient_ids)
        with lock:
            in_flight += 1
            max_in_flight = max(max_in_flight, in_flight)
        try:
            time.sleep(sleep_per_call)
        finally:
            with lock:
                in_flight -= 1
        rtype = request.url.path.rsplit("/", 1)[-1]
        pid = request.url.params.get("patient")
        return httpx.Response(200, json=_bundle([{"resourceType": rtype, "id": f"{rtype}-{pid}"}]))

    fc = _make_client(handler)
    try:
        start = time.perf_counter()
        resources, errors = fc.scan(patient_count=len(patient_ids), types=TYPES)
        elapsed = time.perf_counter() - start
    finally:
        fc.close()

    assert errors == []
    # Concurrency evidence 1: per-type calls overlapped.
    assert max_in_flight > 1, f"expected overlapping calls, saw max {max_in_flight}"

    # Concurrency evidence 2: wall-time well below the sequential lower bound.
    # Sequential would be >= N_patients * N_types * sleep_per_call.
    sequential_lb = len(patient_ids) * len(TYPES) * sleep_per_call
    assert elapsed < sequential_lb * 0.6, (
        f"elapsed {elapsed:.3f}s not far below sequential {sequential_lb:.3f}s"
    )


def test_empty_patient_set_returns_empty():
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/Patient"):
            return _patient_search_response([])
        pytest.fail("no per-type fetch should happen with zero patients")

    fc = _make_client(handler)
    try:
        resources, errors = fc.scan(patient_count=5, types=TYPES)
    finally:
        fc.close()

    assert resources == []
    assert errors == []
