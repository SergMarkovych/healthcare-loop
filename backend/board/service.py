"""
Board service — assembles the Patient Context Board from the FHIR substrate.

Reuses the existing engine read-only: latest-scan resources for the patient
(service.current_resources_for_patient) + the patient-filtered diff of the last
two scans (service.diff_last_two -> diff.filter_for_patient). The cards layer
adds no clinical content; it restates these facts with source references.
"""

from backend.board import cards
from backend.fhir import diff as diffmod
from backend.fhir import service as fhir_service


def _empty_pdiff() -> dict:
    return {"new": [], "updated": [], "not_returned": [], "counts": {}}


def get_board(patient_id: str) -> dict:
    patient, current_resources = fhir_service.current_resources_for_patient(patient_id)
    if patient is None and not current_resources:
        return {"status": "no_scans", "mode": "deterministic",
                "patient": {"id": patient_id, "name": None}, "cards": [], "sources": []}

    full = fhir_service.diff_last_two()
    pdiff = (diffmod.filter_for_patient(full["diff"], patient_id)
             if full.get("status") == "ok" else _empty_pdiff())

    card_list = cards.build_cards(patient, current_resources, pdiff)

    sources = sorted({
        item["source_reference"]
        for card in card_list
        for item in card["items"]
        if item.get("source_reference")
    })

    return {
        "status": "ok",
        "mode": "deterministic",
        "patient": {"id": patient_id, "name": cards._display_name(patient)},
        "cards": card_list,
        "sources": sources,
    }
