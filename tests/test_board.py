"""
Patient Context Board cards over fixtures scan_1 vs scan_2.

The board is a pure restatement layer: every card item is source-backed and
carries no clinical interpretation. These tests assert on concrete values
(names, dose change, source refs) and that no forbidden interpretive wording
leaks into the attention items.
"""

import pytest

from backend.board import service as board_service

# Same forbidden-wording family the summarize safety filter guards against.
_FORBIDDEN = [
    "diagnos", "prescrib", "uncontrolled", "recommend", "abnormal", "is normal",
    "elevated", "too high", "too low", "concerning", "worsening", "improving",
    "risk score", "treatment",
]


def _run_two_scans(fhir_service):
    fhir_service.run_scan(source="fixtures", which=1)
    fhir_service.run_scan(source="fixtures", which=2)


def _card(board: dict, card_id: str) -> dict:
    matches = [c for c in board["cards"] if c["id"] == card_id]
    assert matches, f"card {card_id!r} missing from {[c['id'] for c in board['cards']]}"
    return matches[0]


def test_snapshot_card_has_name_condition_and_medication(fresh_store):
    _run_two_scans(fresh_store)
    board = board_service.get_board("synthetic-A")
    assert board["status"] == "ok"
    assert board["patient"] == {"id": "synthetic-A", "name": "Jordan Sample"}

    snap = _card(board, "patient_snapshot")
    texts = [i["text"] for i in snap["items"]]
    assert any("Jordan Sample" in t for t in texts)

    cond_items = [i for i in snap["items"] if "Type 2 diabetes mellitus" in i["text"]]
    assert cond_items, texts
    assert cond_items[0]["source_reference"] == "Condition/cond-A1"

    med_items = [i for i in snap["items"] if i["source_reference"] == "MedicationRequest/med-A1"]
    assert med_items, texts
    assert "Metformin" in med_items[0]["text"]
    assert "1000 mg twice daily" in med_items[0]["text"]


def test_attention_card_flags_med_dose_change_without_interpretation(fresh_store):
    _run_two_scans(fresh_store)
    board = board_service.get_board("synthetic-A")
    attn = _card(board, "attention")

    dose_items = [i for i in attn["items"] if "med-A1" in i["source_reference"]]
    assert dose_items, [i["source_reference"] for i in attn["items"]]
    item = dose_items[0]
    assert "500 mg twice daily" in item["text"]
    assert "1000 mg twice daily" in item["text"]
    assert "->" in item["text"]
    assert item["evidence"]["old"] == "500 mg twice daily"
    assert item["evidence"]["new"] == "1000 mg twice daily"

    low = " ".join(i["text"].lower() for i in attn["items"])
    leaked = [term for term in _FORBIDDEN if term in low]
    assert not leaked, f"attention card leaked interpretive wording: {leaked}"


def test_attention_card_states_observation_value_as_is(fresh_store):
    _run_two_scans(fresh_store)
    board = board_service.get_board("synthetic-A")
    attn = _card(board, "attention")

    creat = [i for i in attn["items"] if i["source_reference"] == "Observation/obs-A2"]
    assert creat, [i["source_reference"] for i in attn["items"]]
    assert "Creatinine" in creat[0]["text"]
    assert "92 umol/L" in creat[0]["text"]


def test_review_queue_reflects_diff_and_omits_other_patients_task(fresh_store):
    _run_two_scans(fresh_store)
    board = board_service.get_board("synthetic-A")
    rq = _card(board, "review_queue")

    refs = {i["source_reference"] for i in rq["items"]}
    assert "Observation/obs-A2" in refs

    new_items = [i for i in rq["items"] if i["evidence"].get("change") == "new"]
    assert any(i["source_reference"] == "Observation/obs-A2" for i in new_items)

    updated_items = [i for i in rq["items"] if i["evidence"].get("change") == "updated"]
    assert any(i["source_reference"] == "MedicationRequest/med-A1" for i in updated_items)

    # task-B1 is attributed to synthetic-B, so it must NOT appear on synthetic-A's board.
    assert "Task/task-B1" not in refs


def test_open_task_surfaces_for_its_own_patient(fresh_store):
    _run_two_scans(fresh_store)
    board = board_service.get_board("synthetic-B")
    rq = _card(board, "review_queue")

    task_items = [i for i in rq["items"] if i["source_reference"] == "Task/task-B1"]
    assert task_items, [i["source_reference"] for i in rq["items"]]

    open_items = [i for i in task_items if i["text"].startswith("Open workflow item")]
    assert open_items, [i["text"] for i in task_items]
    assert "blood pressure log" in open_items[0]["text"]
    assert open_items[0]["evidence"]["status"] == "requested"


def test_sources_are_collected_and_deduped(fresh_store):
    _run_two_scans(fresh_store)
    board = board_service.get_board("synthetic-A")
    assert board["sources"] == sorted(set(board["sources"]))
    assert "MedicationRequest/med-A1" in board["sources"]
    assert "Condition/cond-A1" in board["sources"]


def test_no_scans_returns_neutral_shape(fresh_store):
    board = board_service.get_board("synthetic-A")
    assert board["status"] == "no_scans"
    assert board["cards"] == []
    assert board["sources"] == []
