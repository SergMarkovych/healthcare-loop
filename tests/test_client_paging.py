"""
Total-cap paging tests for FHIRClient.search_patients() / scan().

`patient_count` (a.k.a. `count`) is a TOTAL cap on patients returned, not a
per-page hint. A FHIR server may honor `_count` per page yet still advertise a
Bundle.link[next], so naively chasing next-links up to MAX_BUNDLE_PAGES can
return up to ~5x the requested count. These tests stub the network with
httpx.MockTransport and verify:

  (a) when pages total MORE than N, search_patients(N) returns exactly N,
  (b) when each page returns FEWER than N, we still follow next until we reach
      N (or run out), and
  (c) scan(patient_count=N) only pulls per-type resources for exactly N patients.
"""

import httpx

from backend.fhir.client import FHIRClient

TYPES = ["Condition", "Observation"]


def _bundle(resources: list[dict], next_url: str | None = None) -> dict:
    bundle: dict = {
        "resourceType": "Bundle",
        "type": "searchset",
        "entry": [{"resource": r} for r in resources],
    }
    if next_url is not None:
        bundle["link"] = [{"relation": "next", "url": next_url}]
    return bundle


def _make_client(handler, base_url: str = "https://fhir.example/r4") -> FHIRClient:
    fc = FHIRClient(base_url)
    fc._client = httpx.Client(
        base_url=base_url,
        transport=httpx.MockTransport(handler),
        headers={"Accept": "application/fhir+json"},
    )
    return fc


def _patients(start: int, n: int) -> list[dict]:
    return [{"resourceType": "Patient", "id": f"p{i}"} for i in range(start, start + n)]


def test_search_patients_caps_total_when_pages_exceed_count():
    """5 pages of 14 patients each (70 total) but count=14 -> exactly 14."""
    base = "https://fhir.example/r4"
    per_page = 14
    count = 14

    def handler(request: httpx.Request) -> httpx.Response:
        # Identify the page from a query param we control on the next URL.
        page = int(request.url.params.get("_page", "0"))
        patients = _patients(page * per_page, per_page)
        next_url = f"{base}/Patient?_page={page + 1}" if page < 4 else None
        return httpx.Response(200, json=_bundle(patients, next_url))

    fc = _make_client(handler)
    try:
        result = fc.search_patients(count)
    finally:
        fc.close()

    assert len(result) == count
    assert [p["id"] for p in result] == [f"p{i}" for i in range(count)]


def test_search_patients_follows_next_when_page_underfills():
    """Pages of 3 each; count=8 -> follow next until 8 collected, then stop."""
    base = "https://fhir.example/r4"
    per_page = 3
    count = 8

    requested_pages: list[int] = []

    def handler(request: httpx.Request) -> httpx.Response:
        page = int(request.url.params.get("_page", "0"))
        requested_pages.append(page)
        patients = _patients(page * per_page, per_page)
        # Always advertise a next link (server has "more"); client must stop
        # itself once it has `count`.
        next_url = f"{base}/Patient?_page={page + 1}"
        return httpx.Response(200, json=_bundle(patients, next_url))

    fc = _make_client(handler)
    try:
        result = fc.search_patients(count)
    finally:
        fc.close()

    assert len(result) == count
    assert [p["id"] for p in result] == [f"p{i}" for i in range(count)]
    # 3 + 3 + 3 = 9 >= 8, so exactly 3 pages fetched (pages 0,1,2); no 4th.
    assert requested_pages == [0, 1, 2]


def test_scan_pulls_resources_for_exactly_n_patients():
    """scan(patient_count=N) must fan out over exactly N patients, not 5xN."""
    base = "https://fhir.example/r4"
    per_page = 4
    count = 4
    queried_patient_ids: set[str] = set()

    def handler(request: httpx.Request) -> httpx.Response:
        path = request.url.path
        if path.endswith("/Patient"):
            page = int(request.url.params.get("_page", "0"))
            patients = _patients(page * per_page, per_page)
            next_url = f"{base}/Patient?_page={page + 1}" if page < 4 else None
            return httpx.Response(200, json=_bundle(patients, next_url))
        rtype = path.rsplit("/", 1)[-1]
        pid = request.url.params.get("patient")
        queried_patient_ids.add(pid)
        res = {"resourceType": rtype, "id": f"{rtype}-{pid}"}
        return httpx.Response(200, json=_bundle([res]))

    fc = _make_client(handler)
    try:
        resources, errors = fc.scan(patient_count=count, types=TYPES)
    finally:
        fc.close()

    assert errors == []
    patients = [r for r in resources if r["resourceType"] == "Patient"]
    assert len(patients) == count
    assert {p["id"] for p in patients} == {f"p{i}" for i in range(count)}
    # Per-type fetches happened for exactly the N capped patients, not 5xN.
    assert queried_patient_ids == {f"p{i}" for i in range(count)}
    assert len(resources) == count * (1 + len(TYPES))
