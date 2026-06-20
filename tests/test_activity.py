"""
Patient Activity List (V4 §17.1) via GET /api/fhir/activity.

After two fixture scans the per-patient diff (test_diff.py) is:
  synthetic-A: new=1 (obs-A2), updated=1 (med-A1 dose), not_returned=0           -> volume 2
  synthetic-B: new=2 (task-B1, obs-B2), updated=0,      not_returned=1 (obs-B1)  -> volume 3
  synthetic-C: new=0, updated=0, not_returned=0                                  -> volume 0
synthetic-B also has one open workflow item (Task/task-B1, status 'requested').
synthetic-B -> 'High', synthetic-A -> 'Medium', synthetic-C -> 'Low'.
Rows are returned sorted by change volume descending (High first).
"""


def _two_scans_then_activity(client, fhir_service):
    fhir_service.reset_store()
    fhir_service.run_scan(source="fixtures", which=1)
    fhir_service.run_scan(source="fixtures", which=2)
    resp = client.get("/api/fhir/activity")
    assert resp.status_code == 200
    return resp.json()


def _one_scan_then_activity(client, fhir_service):
    fhir_service.reset_store()
    fhir_service.run_scan(source="fixtures", which=1)
    resp = client.get("/api/fhir/activity")
    assert resp.status_code == 200
    return resp.json()


def _by_id(rows: list[dict]) -> dict[str, dict]:
    return {r["id"]: r for r in rows}


def test_activity_lists_both_patients_with_counts(client):
    from backend.fhir import service as fhir_service

    rows = _two_scans_then_activity(client, fhir_service)
    rows_by_id = _by_id(rows)
    assert set(rows_by_id) == {"synthetic-A", "synthetic-B", "synthetic-C"}
    assert [r["id"] for r in rows] == ["synthetic-B", "synthetic-A", "synthetic-C"]

    a = rows_by_id["synthetic-A"]
    assert (a["new"], a["updated"], a["not_returned"]) == (1, 1, 0)
    assert a["open_workflow"] == 0
    assert a["name"] == "Jordan Sample"

    b = rows_by_id["synthetic-B"]
    assert (b["new"], b["updated"], b["not_returned"]) == (2, 0, 1)
    assert b["open_workflow"] == 1  # Task/task-B1, status 'requested'
    assert b["name"] == "Alex Demo"

    c = rows_by_id["synthetic-C"]
    assert (c["new"], c["updated"], c["not_returned"]) == (0, 0, 0)
    assert c["open_workflow"] == 0
    assert c["name"] == "Riley Synthetic"

    fhir_service.reset_store()


def test_activity_counts_match_global_diff(client):
    """Per-patient counts must sum to the /api/fhir/diff totals (V4 §2)."""
    from backend.fhir import service as fhir_service

    rows = _two_scans_then_activity(client, fhir_service)
    diff = client.get("/api/fhir/diff").json()["diff"]["counts"]

    assert sum(r["new"] for r in rows) == diff["new"]
    assert sum(r["updated"] for r in rows) == diff["updated"]
    assert sum(r["not_returned"] for r in rows) == diff["not_returned"]

    fhir_service.reset_store()


def test_activity_attention_level_present(client):
    from backend.fhir import service as fhir_service

    rows = _two_scans_then_activity(client, fhir_service)
    by_id = _by_id(rows)
    for r in rows:
        assert r["data_attention"] in {"Low", "Medium", "High"}
        assert r["last_scan"]  # latest scan_run timestamp present
    # synthetic-B volume 3 -> High; synthetic-A volume 2 -> Medium; unchanged synthetic-C -> Low
    assert by_id["synthetic-A"]["data_attention"] == "Medium"
    assert by_id["synthetic-B"]["data_attention"] == "High"
    assert by_id["synthetic-C"]["data_attention"] == "Low"

    fhir_service.reset_store()


def test_attention_wording_is_data_workflow_not_clinical_risk(client):
    """Attention is data/workflow volume, never clinical risk (V4 §17.1 + §23)."""
    from backend.fhir import service as fhir_service

    rows = _two_scans_then_activity(client, fhir_service)
    keys = {k.lower() for r in rows for k in r}
    assert "data_attention" in keys
    # the attention field must not be framed as clinical risk/severity
    forbidden = {"risk", "clinical_risk", "severity", "acuity", "priority"}
    assert keys.isdisjoint(forbidden)

    levels = {r["data_attention"].lower() for r in rows}
    assert levels.issubset({"low", "medium", "high"})
    assert levels.isdisjoint({"critical", "severe", "urgent", "high-risk"})

    fhir_service.reset_store()


def test_activity_empty_when_no_scans(client):
    from backend.fhir import service as fhir_service

    fhir_service.reset_store()
    resp = client.get("/api/fhir/activity")
    assert resp.status_code == 200
    assert resp.json() == []


def test_activity_single_scan_flags_has_two_scans_false(client):
    """After ONE scan, every row reports has_two_scans=False (UI shows dashes)."""
    from backend.fhir import service as fhir_service

    rows = _one_scan_then_activity(client, fhir_service)
    assert rows  # at least one patient present
    for r in rows:
        assert r["has_two_scans"] is False

    fhir_service.reset_store()


def test_activity_two_scans_flag_true_with_real_counts(client):
    """After TWO scans, has_two_scans=True and counts are the real numbers."""
    from backend.fhir import service as fhir_service

    rows = _two_scans_then_activity(client, fhir_service)
    rows_by_id = _by_id(rows)
    for r in rows:
        assert r["has_two_scans"] is True

    a = rows_by_id["synthetic-A"]
    assert (a["new"], a["updated"], a["not_returned"]) == (1, 1, 0)
    b = rows_by_id["synthetic-B"]
    assert (b["new"], b["updated"], b["not_returned"]) == (2, 0, 1)

    fhir_service.reset_store()


def test_data_attention_thresholds():
    from backend.fhir.service import _data_attention

    assert _data_attention(0) == "Low"
    assert _data_attention(1) == "Medium"
    assert _data_attention(2) == "Medium"
    assert _data_attention(3) == "High"
    assert _data_attention(10) == "High"
