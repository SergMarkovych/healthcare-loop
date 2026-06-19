"""
SYNTHETIC DATA — NOT REAL PATIENT INFORMATION.

Every note below is fabricated for demonstration. Names, dates, and details are
fictional. Do not paste real patient data into this tool during the hackathon —
it is a scaffold, not an approved clinical system, and real PHI is governed by
PHIPA (Ontario) and your clinic's privacy policies.
"""

SAMPLES = [
    {
        "id": "sample-1",
        "title": "Diabetes + hypertension follow-up",
        "note": (
            "Family Medicine — follow-up visit (SYNTHETIC)\n"
            "Patient: Jordan Sample, 58. Seen for routine review of type 2 diabetes and high blood pressure.\n\n"
            "S: Feeling well overall. Home BP readings averaging ~150/92. Reports occasional missed doses of "
            "metformin when busy at work. No chest pain, no visual changes. Feet feel fine, no numbness. "
            "Has not had bloodwork since last year.\n\n"
            "O: BP 148/90 in clinic. Weight stable. Last HbA1c 8.4%. No foot exam done today.\n\n"
            "A/P: Type 2 diabetes, suboptimally controlled. Hypertension, above target.\n"
            "- Increase metformin to 1000 mg twice daily.\n"
            "- Start perindopril 4 mg daily for blood pressure.\n"
            "- Order HbA1c, lipid panel, creatinine/eGFR and urine ACR.\n"
            "- Refer to diabetes education program for medication adherence support.\n"
            "- Patient to monitor home BP twice weekly and bring the log next time.\n"
            "- Recheck in 3 months; sooner if home BP consistently above 160/100.\n"
            "- Advised to return to clinic or go to the ER if severe headache, chest pain, or shortness of breath.\n"
            "- Reminder: diabetic foot exam is overdue and should be booked."
        ),
    },
    {
        "id": "sample-2",
        "title": "Acute viral illness + sick note request",
        "note": (
            "Family Medicine — acute visit (SYNTHETIC)\n"
            "Patient: Alex Demo, 31. Presents with 3 days of sore throat, runny nose, mild cough and low-grade fever.\n\n"
            "S: Symptoms improving since yesterday. Eating and drinking normally. No difficulty breathing, "
            "no chest pain. No known unwell contacts with strep. Requests a note for work for the days missed.\n\n"
            "O: Afebrile in clinic. Throat mildly red, no exudate. Chest clear. Ears normal.\n\n"
            "A/P: Likely viral upper respiratory tract infection.\n"
            "- Supportive care: rest, fluids, acetaminophen or ibuprofen as needed for symptoms.\n"
            "- No antibiotics indicated.\n"
            "- Provide sick note covering the two days already missed.\n"
            "- Return if symptoms worsen, fever persists beyond 5 days, or any trouble breathing.\n"
            "- No routine follow-up needed."
        ),
    },
    {
        "id": "sample-3",
        "title": "New low mood + fatigue",
        "note": (
            "Family Medicine — new concern (SYNTHETIC)\n"
            "Patient: Sam Fictional, 26. Booked to discuss low mood and tiredness over the past 6 weeks.\n\n"
            "S: Describes persistent low mood, poor sleep, low energy and reduced interest in usual activities. "
            "Denies any thoughts of self-harm. Appetite slightly reduced. Work stress is high. No prior mental "
            "health history. Wonders if 'something might be off' with thyroid.\n\n"
            "O: Appears tired but engaged. Affect mildly low. Reactive in conversation.\n\n"
            "A/P: Low mood, likely situational; rule out organic contributors.\n"
            "- Order TSH, CBC and ferritin to screen for reversible causes.\n"
            "- Discussed sleep hygiene and offered referral to counselling.\n"
            "- Provided information on local mental health supports.\n"
            "- Follow up in 2 weeks to review labs and reassess mood.\n"
            "- Safety: advised to seek urgent help or go to the ER if any thoughts of self-harm arise."
        ),
    },
]
