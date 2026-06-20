"""
Synthetic inbound admin requests for the demo queue. No real PHI.
Each request links to a synthetic patient and (where a form is involved) a synthetic
encounter note used to pre-fill it.
"""

REQUESTS = [
    {"id": "req-1", "title": "Sick note — 2 days off work",
     "category": "sick_note", "patient_id": "synthetic-B", "sample_id": "sample-2"},
    {"id": "req-2", "title": "Disability Tax Credit (T2201) certification",
     "category": "disability_tax_credit", "patient_id": "synthetic-A", "sample_id": "sample-1"},
    {"id": "req-3", "title": "Insurer short-term disability form",
     "category": "insurance_std", "patient_id": "synthetic-A", "sample_id": "sample-1"},
    {"id": "req-4", "title": "Prescription renewal — metformin (stable)",
     "category": "rx_renewal_stable", "patient_id": "synthetic-A", "sample_id": None},
    {"id": "req-5", "title": "School accommodation note",
     "category": "school_note", "patient_id": "synthetic-B", "sample_id": "sample-3"},
    {"id": "req-6", "title": "Routine monitoring bloodwork requisition",
     "category": "monitoring_requisition", "patient_id": "synthetic-A", "sample_id": None},
    {"id": "req-7", "title": "Referral — pediatric ENT (hearing loss evaluation)",
     "category": "referral_ent", "patient_id": "synthetic-B", "sample_id": "sample-4"},
]

# Synthetic demographics (stand-in for the FHIR Patient resource) keyed by patient id.
DEMOGRAPHICS = {
    "synthetic-A": {"name": "Jordan Sample", "birthDate": "1968-03-12", "gender": "male"},
    "synthetic-B": {"name": "Alex Demo", "birthDate": "1985-07-22", "gender": "female"},
}
