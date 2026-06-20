"""
Referral intelligence — scope-matching and rejection-risk scoring.

Pain surfaced by physician panel: "I don't know which ENT sees this problem —
so I lose time and it adds no value to care."

This module returns a ranked list of available specialists for a given referral
reason, with a rejection-risk score. Mock data for demo; real impl = EMR /
provider-directory lookup.
"""

_RISK_ORDER = {"low": 0, "medium": 1, "high": 2}

# specialty -> list of specialists. Each carries the scope it accepts so the demo
# can show a meaningful accept/reject split for the same indication.
_DIRECTORY = {
    "ENT": [
        {"specialist_name": "Dr. Priya Anand", "clinic": "Riverside Pediatric Ear Clinic",
         "phone": "555-0101", "accepts": ["pediatric hearing loss", "hearing loss", "ear", "tinnitus"],
         "rejection_risk": "low", "notes": "Pediatric hearing loss is a core focus; accepts referrals."},
        {"specialist_name": "Dr. Marcus Webb", "clinic": "Downtown ENT Associates",
         "phone": "555-0102", "accepts": ["sinusitis", "adult hearing loss", "throat", "tonsil"],
         "rejection_risk": "high",
         "notes": "Adult ENT only, refer to pediatric ear clinic instead."},
        {"specialist_name": "Dr. Lena Ortiz", "clinic": "Northside Head & Neck",
         "phone": "555-0103", "accepts": ["hearing loss", "vertigo", "sinusitis"],
         "rejection_risk": "medium", "notes": "Accepts general ENT; pediatric cases triaged case-by-case."},
    ],
    "Cardiology": [
        {"specialist_name": "Dr. Sam Okafor", "clinic": "Heart Health Partners",
         "phone": "555-0201", "accepts": ["arrhythmia", "palpitations", "atrial fibrillation", "chest pain"],
         "rejection_risk": "low", "notes": "Accepts arrhythmia and general cardiology referrals."},
        {"specialist_name": "Dr. Helen Cho", "clinic": "Valley Cardiac Surgery Center",
         "phone": "555-0202", "accepts": ["valve replacement", "bypass", "surgical"],
         "rejection_risk": "high",
         "notes": "Surgical cardiology only; medical management referrals declined, refer to general cardiology."},
        {"specialist_name": "Dr. Raj Patel", "clinic": "Community Cardiology",
         "phone": "555-0203", "accepts": ["hypertension", "chest pain", "arrhythmia"],
         "rejection_risk": "medium", "notes": "General cardiology; longer wait, may decline urgent cases."},
    ],
    "Endocrinology": [
        {"specialist_name": "Dr. Nadia Rahman", "clinic": "Metabolic & Diabetes Center",
         "phone": "555-0301", "accepts": ["diabetes", "thyroid", "insulin", "hba1c"],
         "rejection_risk": "low", "notes": "Accepts diabetes and thyroid referrals."},
        {"specialist_name": "Dr. Tom Briggs", "clinic": "Pituitary & Adrenal Specialists",
         "phone": "555-0302", "accepts": ["pituitary", "adrenal", "rare endocrine"],
         "rejection_risk": "high",
         "notes": "Tertiary endocrine only; routine diabetes referrals declined, refer to diabetes center."},
    ],
    "Neurology": [
        {"specialist_name": "Dr. Eva Lindqvist", "clinic": "Regional Neurology Group",
         "phone": "555-0401", "accepts": ["migraine", "headache", "seizure", "epilepsy"],
         "rejection_risk": "low", "notes": "Accepts migraine, seizure and general neurology referrals."},
        {"specialist_name": "Dr. Omar Said", "clinic": "Movement Disorders Institute",
         "phone": "555-0402", "accepts": ["parkinson", "tremor", "movement disorder"],
         "rejection_risk": "medium", "notes": "Movement disorders focus; general neurology triaged, may redirect."},
    ],
}

# specialty -> keywords that map a free-text reason to that specialty.
_SPECIALTY_KEYWORDS = {
    "ENT": ["ent", "ear", "hearing", "sinus", "throat", "tonsil", "nose", "vertigo", "tinnitus"],
    "Cardiology": ["cardio", "heart", "arrhythmia", "palpitation", "chest pain",
                   "atrial fibrillation", "hypertension", "valve"],
    "Endocrinology": ["endocrine", "diabetes", "thyroid", "insulin", "hba1c",
                      "pituitary", "adrenal", "metabolic"],
    "Neurology": ["neuro", "migraine", "headache", "seizure", "epilepsy",
                  "parkinson", "tremor", "movement disorder"],
}


def _match_specialties(reason: str) -> list[str]:
    return [spec for spec, kws in _SPECIALTY_KEYWORDS.items()
            if any(kw in reason for kw in kws)]


def _accepts_scope(specialist: dict, reason: str) -> bool:
    return any(kw in reason for kw in specialist["accepts"])


def _rank(specialists: list[dict], reason: str) -> list[dict]:
    rows = []
    for s in specialists:
        accepts = _accepts_scope(s, reason)
        rows.append({
            "specialist_name": s["specialist_name"],
            "clinic": s["clinic"],
            "phone": s["phone"],
            "specialty": s["_specialty"],
            "accepts_scope": accepts,
            "rejection_risk": s["rejection_risk"],
            "notes": s["notes"],
        })
    rows.sort(key=lambda r: (not r["accepts_scope"], _RISK_ORDER.get(r["rejection_risk"], 3)))
    return rows


def suggest(reason: str, specialty_hint: str = "") -> list[dict]:
    try:
        reason_l = (reason or "").lower()
        hint_l = (specialty_hint or "").strip().lower()

        if hint_l:
            specialties = [s for s in _DIRECTORY if s.lower() == hint_l]
        else:
            specialties = _match_specialties(reason_l)

        if not specialties:
            return []

        pool = []
        for spec in specialties:
            for s in _DIRECTORY.get(spec, []):
                pool.append({**s, "_specialty": spec})
        return _rank(pool, reason_l)
    except Exception:
        return []
