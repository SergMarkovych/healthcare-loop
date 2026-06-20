"""
Patient Context Board cards over fixtures scan_1 vs scan_2.

Canonical V4 5-card shape (docs/design/v4-board-ui.md §3):
  patient_snapshot, new_updated, open_workflow, limitations, source_references.

The board is a pure restatement layer: every card item is source-backed and
carries no clinical interpretation. These tests assert on concrete values
(names, prev -> current dose change, source refs, limitations) and that the
rules engine is wired in (top-level "flags"). No forbidden interpretive wording
may leak into any card item.
"""

from backend.board import service as board_service

# Same forbidden-wording family the summarize safety filter guards against.
_FORBIDDEN = [
    "diagnos", "prescrib", "uncontrolled", "recommend", "abnormal", "is normal",
    "elevated", "too high", "too low", "concerning", "worsening", "improving",
    "risk score", "treatment",
]

_CARD_IDS = ["patient_snapshot", "new_updated", "open_workflow", "limitations", "source_references"]


def _run_two_scans(fhir_service):
    fhir_service.run_scan(source="fixtures", which=1)
    fhir_service.run_scan(source="fixtures", which=2)


def _card(board: dict, card_id: str) -> dict:
    matches = [c for c in board["cards"] if c["id"] == card_id]
    assert matches, f"card {card_id!r} missing from {[c['id'] for c in board['cards']]}"
    return matches[0]


def _all_text(card: dict) -> str:
    return " ".join(i.get("text", "") for i in card["items"]).lower()


def test_board_has_canonical_five_cards_in_order(fresh_store):
    _run_two_scans(fresh_store)
    board = board_service.get_board("synthetic-A")
    assert board["status"] == "ok"
    assert [c["id"] for c in board["cards"]] == _CARD_IDS


def test_snapshot_card_has_name_condition_and_medication(fresh_store):
    _run_two_scans(fresh_store)
    board = board_service.get_board("synthetic-A")
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


def test_new_updated_card_shows_metformin_prev_to_current(fresh_store):
    _run_two_scans(fresh_store)
    board = board_service.get_board("synthetic-A")
    nu = _card(board, "new_updated")

    upd = [i for i in nu["items"] if i["source_reference"] == "MedicationRequest/med-A1"]
    assert upd, [i["source_reference"] for i in nu["items"]]
    item = upd[0]
    assert item["change_status"] == "updated"
    # previous -> current shown verbatim in the item text.
    assert "500 mg twice daily" in item["text"]
    assert "1000 mg twice daily" in item["text"]
    assert "->" in item["text"]
    # structured prev/current pair, source-backed.
    change = item["changes"][0]
    assert change["path"] == "dosageInstruction[0].text"
    assert change["previous"] == "500 mg twice daily"
    assert change["current"] == "1000 mg twice daily"
    # best-effort source query hint.
    assert item["source_query"] == "MedicationRequest?patient=synthetic-A"
    assert item["evidence"]["change_count"] == 1


def test_new_updated_card_states_new_resource_returned(fresh_store):
    _run_two_scans(fresh_store)
    board = board_service.get_board("synthetic-A")
    nu = _card(board, "new_updated")

    new_items = [i for i in nu["items"] if i["source_reference"] == "Observation/obs-A2"]
    assert new_items, [i["source_reference"] for i in nu["items"]]
    item = new_items[0]
    assert item["change_status"] == "new"
    assert item["text"] == "New Observation returned since last scan."
    assert item["source_query"] == "Observation?patient=synthetic-A"


def test_open_workflow_card_surfaces_open_task_for_its_patient(fresh_store):
    _run_two_scans(fresh_store)
    board = board_service.get_board("synthetic-B")
    ow = _card(board, "open_workflow")

    task_items = [i for i in ow["items"] if i["source_reference"] == "Task/task-B1"]
    assert task_items, [i["source_reference"] for i in ow["items"]]
    item = task_items[0]
    assert item["text"].startswith("Open workflow item")
    assert "blood pressure log" in item["text"]
    assert item["evidence"]["status"] == "requested"


def test_open_workflow_omits_other_patients_task(fresh_store):
    _run_two_scans(fresh_store)
    board = board_service.get_board("synthetic-A")
    ow = _card(board, "open_workflow")
    refs = {i["source_reference"] for i in ow["items"]}
    # task-B1 belongs to synthetic-B; it must not appear on synthetic-A's board.
    assert "Task/task-B1" not in refs


def test_limitations_card_lists_not_returned_and_absent_types(fresh_store):
    _run_two_scans(fresh_store)
    # synthetic-A: Task is requested (CORE_TYPES) but absent from this patient's resources.
    board = board_service.get_board("synthetic-A")
    lim = _card(board, "limitations")
    absent = [i for i in lim["items"] if i["evidence"].get("requested_type_absent") == "Task"]
    assert absent, [i["text"] for i in lim["items"]]
    assert "not deleted" in absent[0]["text"]
    assert lim["data_source_limitations"] == ["Task not returned by current API response."]

    # synthetic-B: Observation/obs-B1 present in scan_1, dropped in scan_2 -> not_returned key.
    board_b = board_service.get_board("synthetic-B")
    lim_b = _card(board_b, "limitations")
    nr = [i for i in lim_b["items"] if i["source_reference"] == "Observation/obs-B1"]
    assert nr, [i["text"] for i in lim_b["items"]]
    assert "not deleted" in nr[0]["text"]
    assert nr[0]["evidence"]["change"] == "not_returned"


def test_source_references_card_is_deduped_provenance(fresh_store):
    _run_two_scans(fresh_store)
    board = board_service.get_board("synthetic-A")
    src = _card(board, "source_references")

    refs = [i["source_reference"] for i in src["items"]]
    assert refs == sorted(set(refs))
    assert "MedicationRequest/med-A1" in refs
    assert "Condition/cond-A1" in refs
    assert "Observation/obs-A2" in refs
    # every source-references item carries a query hint.
    assert all("?patient=synthetic-A" in i["source_query"] for i in src["items"])


def test_top_level_flags_contains_resource_updated_for_med_a1(fresh_store):
    _run_two_scans(fresh_store)
    board = board_service.get_board("synthetic-A")
    assert "flags" in board

    updated = [
        f for f in board["flags"]
        if f["ruleId"] == "resource_updated" and f["source"] == "MedicationRequest/med-A1"
    ]
    assert updated, board["flags"]
    flag = updated[0]
    assert flag["category"] == "data_change"
    assert flag["changeStatus"] == "updated"
    assert "500 mg twice daily" in flag["message"]
    assert "1000 mg twice daily" in flag["message"]
    assert flag["clinicalInterpretation"] is None
    assert flag["treatmentRecommendation"] is None


def test_sources_top_level_collected_and_deduped(fresh_store):
    _run_two_scans(fresh_store)
    board = board_service.get_board("synthetic-A")
    assert board["sources"] == sorted(set(board["sources"]))
    assert "MedicationRequest/med-A1" in board["sources"]
    assert "Condition/cond-A1" in board["sources"]


def test_no_fabricated_clinical_wording_in_any_card(fresh_store):
    _run_two_scans(fresh_store)
    for patient_id in ("synthetic-A", "synthetic-B"):
        board = board_service.get_board(patient_id)
        for card in board["cards"]:
            low = _all_text(card)
            leaked = [term for term in _FORBIDDEN if term in low]
            assert not leaked, f"card {card['id']} leaked interpretive wording: {leaked}"


def test_no_scans_returns_neutral_shape(fresh_store):
    board = board_service.get_board("synthetic-A")
    assert board["status"] == "no_scans"
    assert board["cards"] == []
    assert board["flags"] == []
    assert board["sources"] == []
