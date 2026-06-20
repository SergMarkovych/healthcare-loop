"""
Close-the-loop write-back: builder + writer + the action endpoints.

Offline discipline: WRITE_ENABLED is unset for the suite (conftest never sets it),
so the writer stays in mock mode and no test touches the network. The one test
that exercises the write path forces WRITE_ENABLED on but FHIR_BASE_URL empty,
which is still a mock create (write enabled, no live server) — no socket opened.
"""

import backend.fhir.action_builder as ab
import backend.fhir.writer as writer


# --- builder: right resourceType + required fields for all 4 kinds ----------

def test_build_task_shape():
    res = ab.build("task", "p1", {"description": "Confirm CRA receipt", "owner": "admin"})
    assert res["resourceType"] == "Task"
    assert res["status"] == "requested"
    assert res["intent"] == "order"
    assert res["description"] == "Confirm CRA receipt"
    assert res["for"] == {"reference": "Patient/p1"}
    assert res["owner"] == {"display": "admin"}
    assert res["authoredOn"].endswith("Z")


def test_build_service_request_shape():
    res = ab.build("service_request", "p2", {"code_text": "CBC + ferritin", "reason": "monitoring"})
    assert res["resourceType"] == "ServiceRequest"
    assert res["status"] == "active"
    assert res["intent"] == "order"
    assert res["subject"] == {"reference": "Patient/p2"}
    assert res["code"] == {"text": "CBC + ferritin"}
    assert res["reasonCode"] == [{"text": "monitoring"}]


def test_build_communication_request_shape():
    res = ab.build("communication_request", "p3", {"message": "Your results are normal."})
    assert res["resourceType"] == "CommunicationRequest"
    assert res["status"] == "active"
    assert res["subject"] == {"reference": "Patient/p3"}
    assert res["payload"] == [{"contentString": "Your results are normal."}]
    assert res["requester"] == {"display": "Physician"}


def test_build_questionnaire_response_shape():
    res = ab.build("questionnaire_response", "p4", {
        "questionnaire_id": "sick_note",
        "items": [{"linkId": "patient_name", "text": "Patient name", "value": "Alex Demo"},
                  {"linkId": "expected_duration", "text": "Expected duration", "value": "2 days"}],
    })
    assert res["resourceType"] == "QuestionnaireResponse"
    assert res["status"] == "completed"
    assert res["questionnaire"] == "Questionnaire/sick_note"
    assert res["subject"] == {"reference": "Patient/p4"}
    assert res["item"][0] == {"linkId": "patient_name", "text": "Patient name",
                              "answer": [{"valueString": "Alex Demo"}]}
    assert res["item"][1]["answer"] == [{"valueString": "2 days"}]


def test_build_unknown_kind_raises():
    import pytest
    with pytest.raises(ValueError):
        ab.build("nope", "p1", {})


def test_build_transaction_bundle_shape():
    task = ab.build("task", "p1", {"description": "x"})
    sr = ab.build("service_request", "p1", {"code_text": "CBC"})
    bundle = ab.build_transaction_bundle([task, sr])
    assert bundle["resourceType"] == "Bundle"
    assert bundle["type"] == "transaction"
    assert len(bundle["entry"]) == 2
    assert bundle["entry"][0]["request"] == {"method": "POST", "url": "Task"}
    assert bundle["entry"][1]["request"] == {"method": "POST", "url": "ServiceRequest"}
    assert bundle["entry"][0]["resource"] is task


# --- writer: mock returns a simulated id, never hits the network ------------

def test_writer_mock_returns_simulated_id():
    res = ab.build("task", "p1", {"description": "x"})
    out = writer.create(res)
    assert out["status"] == "created"
    assert out["mode"] == "mock"
    assert out["id"].startswith("mock-task-")
    assert out["location"] == f"Task/{out['id']}"
    assert out["resource"]["id"] == out["id"]


def test_writer_mock_does_not_open_socket(monkeypatch):
    # Any network attempt would call httpx.post; assert it is never reached.
    def _boom(*a, **k):
        raise AssertionError("writer hit the network in mock mode")

    monkeypatch.setattr(writer.httpx, "post", _boom)
    res = ab.build("communication_request", "p1", {"message": "hi"})
    out = writer.create(res)
    assert out["mode"] == "mock"


def test_writer_transaction_mock():
    bundle = ab.build_transaction_bundle([
        ab.build("task", "p1", {"description": "x"}),
        ab.build("service_request", "p1", {"code_text": "CBC"}),
    ])
    out = writer.transaction(bundle)
    assert out["mode"] == "mock"
    assert out["count"] == 2
    assert all("/" in loc for loc in out["locations"])


def test_writer_create_no_resource_type_errors():
    out = writer.create({"foo": "bar"})
    assert out["status"] == "error"


# --- endpoints --------------------------------------------------------------

def test_action_endpoint_mock(client):
    r = client.post("/api/fhir/action", json={
        "kind": "task", "patient_id": "synthetic-A",
        "payload": {"description": "Submit T2201"},
    })
    assert r.status_code == 200
    d = r.json()
    assert d["mode"] == "mock"
    assert d["kind"] == "task"
    assert d["resource"]["resourceType"] == "Task"
    assert d["resource"]["description"] == "Submit T2201"
    assert d["resource"]["id"].startswith("mock-task-")
    assert d["result"]["mode"] == "mock"


def test_action_endpoint_unknown_kind(client):
    r = client.post("/api/fhir/action", json={"kind": "nope", "patient_id": "p", "payload": {}})
    assert r.json()["status"] == "error"


def test_action_batch_endpoint_mock(client):
    r = client.post("/api/fhir/action/batch", json={"actions": [
        {"kind": "task", "patient_id": "p1", "payload": {"description": "x"}},
        {"kind": "communication_request", "patient_id": "p1", "payload": {"message": "hi"}},
    ]})
    assert r.status_code == 200
    d = r.json()
    assert d["count"] == 2
    assert d["mode"] == "mock"
    assert d["result"]["count"] == 2


# --- office approve with write-back -----------------------------------------

def test_approve_without_write_enabled_has_no_written_block(client):
    r = client.post("/api/office/approve", json={"request_id": "req-2", "completed_fields": {}})
    d = r.json()
    assert d["status"] == "ok"
    assert "written" not in d  # default behavior unchanged when WRITE_ENABLED off


def test_approve_with_mock_write_includes_simulated_task_id(client, monkeypatch):
    # Enable writes but force mock (no live server) so this stays offline.
    monkeypatch.setenv("WRITE_ENABLED", "1")
    monkeypatch.setenv("FHIR_BASE_URL", "")

    def _boom(*a, **k):
        raise AssertionError("approve write-back hit the network")

    monkeypatch.setattr(writer.httpx, "post", _boom)

    r = client.post("/api/office/approve", json={
        "request_id": "req-2",
        "completed_fields": {
            "onset_date": "2019-05",
            "functional_limitations": "Marked restriction walking >100m.",
            "prognosis": "Chronic; no full recovery expected.",
        },
    })
    d = r.json()
    assert d["status"] == "ok"
    w = d["written"]
    assert w["mode"] == "mock"
    assert w["task_id"].startswith("mock-task-")
    assert w["questionnaire_response_id"].startswith("mock-questionnaireresponse-")
    assert w["task_location"] == f"Task/{w['task_id']}"
