"""Approve -> draft + follow-up task. The actionable step, and its safety invariant:
clinical fields the physician leaves blank are reported outstanding, never invented."""


def test_approve_dtc_complete(client):
    r = client.post("/api/office/approve", json={
        "request_id": "req-2",
        "completed_fields": {
            "onset_date": "2019-05",
            "functional_limitations": "Marked restriction walking >100m; needs frequent rest.",
            "prognosis": "Chronic, progressive; no full recovery expected.",
        },
    })
    assert r.status_code == 200
    d = r.json()
    assert d["status"] == "ok"

    draft = d["draft"]
    assert draft["complete"] is True
    assert draft["outstanding_fields"] == []
    fl = next(f for f in draft["fields"] if f["id"] == "functional_limitations")
    assert fl["value"].startswith("Marked restriction")
    assert fl["completed_by_physician"] is True

    task = d["follow_up_task"]
    assert task["source_request"] == "req-2"
    assert task["owner"] == "admin"
    assert task["status"] == "open"
    assert task["title"]


def test_approve_dtc_incomplete_reports_outstanding_never_invents(client):
    r = client.post("/api/office/approve", json={"request_id": "req-2", "completed_fields": {}})
    d = r.json()
    draft = d["draft"]
    assert draft["complete"] is False
    assert {"Date of onset", "Functional limitations", "Prognosis"} <= set(draft["outstanding_fields"])
    for f in draft["fields"]:
        if f["needs_physician"]:
            assert f["value"] == ""
            assert f["completed_by_physician"] is False


def test_approve_no_form_passthrough(client):
    r = client.post("/api/office/approve", json={"request_id": "req-4"})  # rx renewal, no form
    assert r.json()["status"] == "no_form"


def test_approve_unknown_request_not_found(client):
    r = client.post("/api/office/approve", json={"request_id": "nope"})
    assert r.json()["status"] == "not_found"
