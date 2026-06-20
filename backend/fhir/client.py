"""
Minimal FHIR R4 REST client.

Talks to any FHIR R4 base URL — the public HAPI test server for the fast path,
or a local HAPI loaded with Synthea for the controlled demo. Pulls a patient
list and the core clinical resource types per patient.

Note: in restricted sandboxes the live server may be unreachable; the app's
fixtures path (`source=fixtures`) provides an offline, deterministic scan that
exercises the same snapshot/diff/summary pipeline.
"""

from concurrent.futures import ThreadPoolExecutor

import httpx

DEFAULT_TYPES = [
    "Condition", "MedicationRequest", "Observation", "Encounter",
    "Task", "ServiceRequest", "DiagnosticReport", "DocumentReference", "Appointment",
]
# A smaller set keeps the MVP scan fast; extend toward DEFAULT_TYPES as time allows.
CORE_TYPES = ["Condition", "MedicationRequest", "Observation", "Encounter", "Task"]

# §14: cap how many Bundle pages we'll chase so a misbehaving server / huge
# patient cannot wedge a scan. Each page is one network round-trip.
MAX_BUNDLE_PAGES = 5


def _next_link(bundle: dict) -> str | None:
    """Absolute URL of the Bundle's next page, or None when exhausted (§14)."""
    for link in bundle.get("link", []) or []:
        if isinstance(link, dict) and link.get("relation") == "next":
            url = link.get("url")
            return url if isinstance(url, str) and url else None
    return None


def _entries(bundle: dict) -> list[dict]:
    return [e["resource"] for e in bundle.get("entry", []) or [] if "resource" in e]


class FetchError(dict):
    """A recorded per-type fetch failure (§21). dict-shaped for easy persistence."""


class FHIRClient:
    def __init__(self, base_url: str, timeout: float = 30.0):
        self.base_url = base_url.rstrip("/")
        self._client = httpx.Client(
            base_url=self.base_url,
            timeout=timeout,
            headers={"Accept": "application/fhir+json"},
        )

    def capability(self) -> dict:
        r = self._client.get("/metadata", params={"_summary": "true"})
        r.raise_for_status()
        return r.json()

    def _paged(self, path: str, params: dict) -> list[dict]:
        """Fetch a search set, following Bundle.link[next] up to MAX_BUNDLE_PAGES.

        First request goes through the path + params (relative to base_url);
        subsequent pages use the server's absolute next URL verbatim (§14).
        """
        out: list[dict] = []
        r = self._client.get(path, params=params)
        r.raise_for_status()
        bundle = r.json()
        out += _entries(bundle)
        pages = 1
        next_url = _next_link(bundle)
        while next_url and pages < MAX_BUNDLE_PAGES:
            r = self._client.get(next_url)  # absolute URL; httpx ignores base_url
            r.raise_for_status()
            bundle = r.json()
            out += _entries(bundle)
            pages += 1
            next_url = _next_link(bundle)
        return out

    def search_patients(self, count: int = 10) -> list[dict]:
        """Return at most `count` patients in TOTAL across all Bundle pages.

        `_count` is the server's per-page hint, not a guarantee: a page may
        return fewer than `count`, so we keep following Bundle.link[next] until
        we have `count` patients or run out (bounded by MAX_BUNDLE_PAGES, §14).
        Conversely a server may honor `_count` per page yet still advertise a
        next link, so we stop chasing once `count` are collected and slice the
        result to exactly `count` — never exceeding the requested cap.
        """
        if count <= 0:
            return []
        out: list[dict] = []
        r = self._client.get("/Patient", params={"_count": count})
        r.raise_for_status()
        bundle = r.json()
        out += _entries(bundle)
        pages = 1
        next_url = _next_link(bundle)
        while len(out) < count and next_url and pages < MAX_BUNDLE_PAGES:
            r = self._client.get(next_url)  # absolute URL; httpx ignores base_url
            r.raise_for_status()
            bundle = r.json()
            out += _entries(bundle)
            pages += 1
            next_url = _next_link(bundle)
        return out[:count]

    def resources_for_patient(
        self, patient_id: str, types: list[str], per_type: int = 50,
        errors: list[dict] | None = None,
    ) -> list[dict]:
        out: list[dict] = []
        for rtype in types:
            try:
                out += self._paged(f"/{rtype}", {"patient": patient_id, "_count": per_type})
            except httpx.HTTPError as err:
                # §21: surface the failure instead of swallowing to a print. An
                # unsupported/empty type is benign, but the caller decides — it
                # may persist a change_status='error' diff row for this (type,patient).
                fe: dict = FetchError(
                    resource_type=rtype, patient_id=patient_id, error=str(err),
                )
                if errors is not None:
                    errors.append(fe)
                else:
                    print(f"[fhir.client] {rtype} for {patient_id}: {err}")
        return out

    def scan(
        self, patient_count: int = 5, types: list[str] | None = None,
    ) -> tuple[list[dict], list[dict]]:
        """Return (resources, errors). errors is one record per failed per-type fetch.

        Patients are fetched concurrently via a bounded ThreadPoolExecutor (§14):
        a live scan is ~patients × types sequential GETs, which times out against a
        slow server. httpx.Client is thread-safe for issuing requests, so the single
        shared self._client is reused across workers.

        Content is identical to the sequential version: each patient still yields its
        patient resource followed by that patient's resources_for_patient output, and
        every per-type failure is surfaced into errors. Only the inter-patient ORDER
        may differ — the diff layer keys by resource_key, so it is order-independent.
        """
        types = types or CORE_TYPES
        patients = self.search_patients(patient_count)
        if not patients:
            return [], []

        def _one(patient: dict) -> tuple[list[dict], list[dict]]:
            local_errors: list[dict] = []
            block: list[dict] = [patient]
            block += self.resources_for_patient(
                patient["id"], types, errors=local_errors,
            )
            return block, local_errors

        resources: list[dict] = []
        errors: list[dict] = []
        max_workers = min(8, len(patients))
        with ThreadPoolExecutor(max_workers=max_workers) as pool:
            for block, local_errors in pool.map(_one, patients):
                resources += block
                errors += local_errors
        return resources, errors

    def close(self):
        self._client.close()
