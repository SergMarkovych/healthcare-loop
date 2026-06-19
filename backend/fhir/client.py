"""
Minimal FHIR R4 REST client.

Talks to any FHIR R4 base URL — the public HAPI test server for the fast path,
or a local HAPI loaded with Synthea for the controlled demo. Pulls a patient
list and the core clinical resource types per patient.

Note: in restricted sandboxes the live server may be unreachable; the app's
fixtures path (`source=fixtures`) provides an offline, deterministic scan that
exercises the same snapshot/diff/summary pipeline.
"""

import httpx

DEFAULT_TYPES = [
    "Condition", "MedicationRequest", "Observation", "Encounter",
    "Task", "ServiceRequest", "DiagnosticReport", "DocumentReference", "Appointment",
]
# A smaller set keeps the MVP scan fast; extend toward DEFAULT_TYPES as time allows.
CORE_TYPES = ["Condition", "MedicationRequest", "Observation", "Encounter", "Task"]


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

    def search_patients(self, count: int = 10) -> list[dict]:
        r = self._client.get("/Patient", params={"_count": count})
        r.raise_for_status()
        bundle = r.json()
        return [e["resource"] for e in bundle.get("entry", []) if "resource" in e]

    def resources_for_patient(self, patient_id: str, types: list[str], per_type: int = 50) -> list[dict]:
        out: list[dict] = []
        for rtype in types:
            try:
                r = self._client.get(f"/{rtype}", params={"patient": patient_id, "_count": per_type})
                r.raise_for_status()
                bundle = r.json()
                out += [e["resource"] for e in bundle.get("entry", []) if "resource" in e]
            except httpx.HTTPError as err:
                # An unsupported/empty resource type is normal — record nothing, continue.
                print(f"[fhir.client] {rtype} for {patient_id}: {err}")
        return out

    def scan(self, patient_count: int = 5, types: list[str] | None = None) -> list[dict]:
        types = types or CORE_TYPES
        resources: list[dict] = []
        for patient in self.search_patients(patient_count):
            resources.append(patient)
            resources += self.resources_for_patient(patient["id"], types)
        return resources

    def close(self):
        self._client.close()
