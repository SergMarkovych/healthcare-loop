"""
The "measured moment" — turn the work into hours, the language the Developer Guide's
clinical-importance criterion rewards (19 h/wk, ~47% unnecessary, ~9,093 FTE).

Numbers are illustrative baselines for a demo, stated openly. They are NOT a study;
on event day, calibrate them with the clinician SMEs in the room.
"""

# category -> (manual_minutes, assisted_minutes) per task
_BASELINE = {
    "sick_note": (6, 0),                  # eliminated: ~0 physician minutes
    "rx_renewal_stable": (5, 1),
    "monitoring_requisition": (4, 0),
    "disability_tax_credit": (22, 4),     # pre-filled, physician reviews clinical fields
    "insurance_std": (15, 4),
    "school_note": (8, 2),
    "referral_ent": (18, 3),              # manual: 18 min to find + fill referral; assisted: 3 min
}

# Rough annual volume per physician (illustrative) to project recovered capacity.
_ANNUAL_VOLUME = {
    "sick_note": 250, "rx_renewal_stable": 1200, "monitoring_requisition": 300,
    "disability_tax_credit": 30,
    "insurance_std": 120, "school_note": 60, "referral_ent": 80,
}
_PHYSICIAN_MINUTES_PER_YEAR = 1800 * 60  # ~1800 clinical hours/yr, for FTE projection


def per_task(category: str, route: str) -> dict:
    manual, assisted = _BASELINE.get(category, (10, 3))
    saved = max(manual - assisted, 0)
    touch_avoided = 1 if route in ("eliminate", "delegate", "automate") else 0
    return {"manual_minutes": manual, "assisted_minutes": assisted,
            "saved_minutes": saved, "touchpoint_avoided": touch_avoided}


def project_annual(processed: list[dict]) -> dict:
    """processed: list of {category, route}. Returns aggregate + a clinic-level projection."""
    total_saved = 0
    total_touch = 0
    annual_saved_minutes = 0
    for item in processed:
        m = per_task(item["category"], item["route"])
        total_saved += m["saved_minutes"]
        total_touch += m["touchpoint_avoided"]
        annual_saved_minutes += m["saved_minutes"] * _ANNUAL_VOLUME.get(item["category"], 100)
    fte = round(annual_saved_minutes / _PHYSICIAN_MINUTES_PER_YEAR, 2)
    return {
        "tasks_processed": len(processed),
        "minutes_saved_now": total_saved,
        "physician_touchpoints_avoided": total_touch,
        "projected_annual_hours_per_physician": round(annual_saved_minutes / 60),
        "projected_fte_per_100_physicians": round(fte * 100, 1),
        "assumptions": "Illustrative per-task baselines and annual volumes; calibrate with clinician SMEs.",
    }
