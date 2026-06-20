"""
Action builder — turn an approved item into a *draft* FHIR R4 resource.

The system never invents clinical content: it assembles administrative/workflow
resources (a follow-up Task, a requisition, a patient message, a completed form)
from fields the physician has reviewed. Building a resource does not write it;
the FHIR Writer (writer.py) does that, and only after the physician approves.

Pure module: no I/O, no network, no env reads — every function is a deterministic
transform from inputs to a dict, so the builder is trivially testable offline.
"""

from datetime import datetime, timezone


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _ref(patient_id: str) -> dict:
    return {"reference": f"Patient/{patient_id}"}


def build_task(patient_id: str, description: str, *, focus: str | None = None,
               owner: str = "Nursing / admin queue", requester: str = "Physician",
               priority: str = "routine") -> dict:
    res = {
        "resourceType": "Task",
        "status": "requested",
        "intent": "order",
        "priority": priority,
        "description": description,
        "for": _ref(patient_id),
        "authoredOn": _now(),
        "requester": {"display": requester},
        "owner": {"display": owner},
    }
    if focus:
        res["focus"] = {"reference": focus}
    return res


def build_service_request(patient_id: str, code_text: str, *, reason: str = "",
                          priority: str = "routine") -> dict:
    res = {
        "resourceType": "ServiceRequest",
        "status": "active",
        "intent": "order",
        "priority": priority,
        "subject": _ref(patient_id),
        "code": {"text": code_text},
        "authoredOn": _now(),
    }
    if reason:
        res["reasonCode"] = [{"text": reason}]
    return res


def build_communication_request(patient_id: str, message: str, *,
                                requester: str = "Physician") -> dict:
    return {
        "resourceType": "CommunicationRequest",
        "status": "active",
        "subject": _ref(patient_id),
        "payload": [{"contentString": message}],
        "authoredOn": _now(),
        "requester": {"display": requester},
    }


def build_questionnaire_response(patient_id: str, questionnaire_id: str,
                                 items: list[dict]) -> dict:
    """items: [{linkId, text, value}] -> QuestionnaireResponse.item[*].answer[valueString]."""
    return {
        "resourceType": "QuestionnaireResponse",
        "questionnaire": f"Questionnaire/{questionnaire_id}",
        "status": "completed",
        "subject": _ref(patient_id),
        "authored": _now(),
        "item": [
            {"linkId": it.get("linkId", ""),
             "text": it.get("text", ""),
             "answer": [{"valueString": str(it.get("value", ""))}]}
            for it in items
        ],
    }


def build_transaction_bundle(actions: list[dict]) -> dict:
    """Wrap several built resources for an atomic write (all succeed or all fail)."""
    return {
        "resourceType": "Bundle",
        "type": "transaction",
        "entry": [
            {"resource": r, "request": {"method": "POST", "url": r["resourceType"]}}
            for r in actions
        ],
    }


# Dispatch table for the API: kind -> builder(patient_id, payload) -> resource
def build(kind: str, patient_id: str, payload: dict) -> dict:
    if kind == "task":
        return build_task(patient_id, payload.get("description", "Follow-up task"),
                          focus=payload.get("focus"),
                          owner=payload.get("owner", "Nursing / admin queue"),
                          priority=payload.get("priority", "routine"))
    if kind == "service_request":
        return build_service_request(patient_id, payload.get("code_text", "Investigation"),
                                     reason=payload.get("reason", ""),
                                     priority=payload.get("priority", "routine"))
    if kind == "communication_request":
        return build_communication_request(patient_id, payload.get("message", ""))
    if kind == "questionnaire_response":
        return build_questionnaire_response(patient_id, payload.get("questionnaire_id", "form"),
                                            payload.get("items", []))
    raise ValueError(f"Unknown action kind: {kind}")
