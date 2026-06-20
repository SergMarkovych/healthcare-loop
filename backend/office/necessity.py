"""
Necessity gate (challenge area #5 — "where AI should start").

The point clinicians made: a lot of paperwork reaches the physician that does not
need a physician at all. Before drafting anything, classify each incoming request:

  - eliminate        : shouldn't require a physician (e.g. short-term sick note);
                       resolve with a patient attestation.
  - delegate         : a team member (nurse / admin / pharmacist) can handle it.
  - automate         : protocol-driven; generate the artifact, physician just signs.
  - physician_review : genuinely needs clinical judgement → prefill + review.

Rules are deterministic and transparent (not a black box) so the routing is
auditable — which is exactly what the "calibrated trust" requirement asks for.

Known categories stay on the deterministic `_RULES` table. Unknown categories are
classified by the LLM into one of the four routes, conservatively defaulting to
physician_review on low confidence or any failure. Mirrors field_drafter's
discipline: enforce the Pydantic JSON schema, validate + retry once, clamp any
out-of-vocabulary route to physician_review, and degrade to the safe default on
any error so the demo never dead-ends. Goes through llm_client.call_chat only.

Config via environment variables:
  FORCE_MOCK  set to 1 to skip the model entirely (deterministic default)
"""

import json
import os

from backend import llm_client
from backend.schema import NecessityRoute

FORCE_MOCK = os.environ.get("FORCE_MOCK", "").lower() in ("1", "true", "yes")

SYSTEM_PROMPT = (
    "You triage one inbound primary-care administrative request into exactly ONE route: "
    "eliminate (no physician needed — e.g. a patient attestation), delegate (a "
    "nurse/admin/pharmacist can handle it), automate (protocol-driven — the physician "
    "only signs), or physician_review (genuinely needs clinical judgement). When "
    "uncertain, choose physician_review. Give `who` (who should handle it) and a "
    "one-sentence `reason`. Return ONLY JSON matching the schema."
)

# category -> (route, who, reason)
_RULES = {
    "sick_note": (
        "eliminate", "patient",
        "Short-term sick notes do not require physician judgement; in Ontario employers "
        "cannot require one for ESA sick leave. Resolve with a patient attestation.",
    ),
    "rx_renewal_stable": (
        "automate", "pharmacist / protocol",
        "Renewal of a stable chronic medication is protocol-driven; generate the renewal "
        "for signature or route under a pharmacist protocol.",
    ),
    "monitoring_requisition": (
        "automate", "standing order",
        "Routine monitoring bloodwork follows a standing schedule; generate the requisition "
        "automatically.",
    ),
    "form_completion_admin": (
        "delegate", "admin",
        "Administrative form fields can be completed by office staff from chart data.",
    ),
    "disability_tax_credit": (
        "physician_review", "physician",
        "Certifying functional limitations requires clinical judgement. Pre-fill the known "
        "fields and route the clinical fields for physician review.",
    ),
    "insurance_std": (
        "physician_review", "physician",
        "An attending-physician statement requires clinical judgement on capacity and "
        "prognosis. Pre-fill known fields; physician completes the clinical fields.",
    ),
    "school_note": (
        "physician_review", "physician",
        "School accommodation depends on a clinical view of the patient's limitations. "
        "Pre-fill demographics and diagnosis; physician confirms the accommodation.",
    ),
    "referral_ent": (
        "physician_review", "physician",
        "Specialist referral requires physician sign-off on scope and urgency. "
        "Referral intelligence surfaces ranked specialist options for this indication.",
    ),
}

ROUTES = ["eliminate", "delegate", "automate", "physician_review"]

_DEFAULT = {
    "route": "physician_review", "who": "physician",
    "reason": "Unrecognized request type — defaulting to physician review.",
    "requires_physician": True,
}


def _messages(category: str) -> list[dict]:
    schema = json.dumps(NecessityRoute.model_json_schema())
    user = (
        "Triage the inbound request below into exactly one route. "
        "Return JSON conforming to this schema:\n"
        f"{schema}\n\n"
        "--- INBOUND REQUEST ---\n"
        f"category/text: {category}\n"
        "--- END REQUEST ---"
    )
    return [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": user},
    ]


def _classify_llm(category: str) -> dict | None:
    """Classify an unknown request via the model. Returns None on FORCE_MOCK or any error.

    The returned route is clamped to ROUTES, falling back to physician_review for any
    out-of-vocabulary value. Never raises.
    """
    if FORCE_MOCK:
        return None

    try:
        messages = _messages(category)
        schema = NecessityRoute.model_json_schema()

        result: NecessityRoute | None = None
        for _ in range(2):
            content = llm_client.call_chat(messages, schema, timeout=60)
            try:
                result = NecessityRoute.model_validate_json(content)
                break
            except Exception as err:  # JSON or schema validation problem
                messages.append({"role": "assistant", "content": content})
                messages.append({
                    "role": "user",
                    "content": (
                        f"That response did not validate against the schema: {err}. "
                        "Return corrected JSON only, no commentary."
                    ),
                })
        if result is None:
            return None

        route = result.route if result.route in ROUTES else "physician_review"
        return {"route": route, "who": result.who, "reason": result.reason,
                "requires_physician": route == "physician_review"}

    except Exception as err:  # connection refused, model not pulled, timeout, etc.
        print(f"[necessity] model unavailable ({err}); defaulting to physician review.")
        return None


def classify(category: str) -> dict:
    if category in _RULES:
        route, who, reason = _RULES[category]
        return {"route": route, "who": who, "reason": reason,
                "requires_physician": route == "physician_review"}

    if not FORCE_MOCK:
        classified = _classify_llm(category)
        if classified is not None:
            return classified

    return dict(_DEFAULT)
