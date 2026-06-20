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
"""

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


def classify(category: str) -> dict:
    route, who, reason = _RULES.get(
        category,
        ("physician_review", "physician", "Unrecognized request type — defaulting to physician review."),
    )
    return {"route": route, "who": who, "reason": reason,
            "requires_physician": route == "physician_review"}
