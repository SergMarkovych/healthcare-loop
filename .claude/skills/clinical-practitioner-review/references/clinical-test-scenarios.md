# Clinical Test Scenarios

Synthetic cases to feed the tool during the review, so the evaluation rests on what it *actually does* with realistic input rather than on what the README claims. **All cases below are fictional and contain no real patient information. Never substitute real PHI** — this also mirrors the COMPASS event rule, which permits *synthetic or de-identified data only, no real patient data, no live EMR connections.*

For a deeper or larger spread of realistic-but-synthetic input, draw from the datasets the COMPASS guide itself recommends: **MTSamples** (5,000+ public-domain SOAP/progress/office notes — ideal raw material for the follow-up extractor) and **Synthea** (synthetic FHIR R4 patient records with real condition/medication/encounter timelines). Both are safe to use freely and make the review's findings more credible to clinician judges.

The point of these is to get past the happy path. Any tool will look good on a clean, single-complaint demo case written by the people who built it. You learn the truth from the messy ones — the patient with nine problems, the note with a gap in it, the presentation that doesn't fit the template. Throw the ugly cases at it on purpose and watch how it behaves at the edges.

For Loop specifically: use the follow-up cases on the extractor at `/`, and the form / office cases on the digital office assistant at `/office`.

---

## How to use these

For each scenario you run, note four things in the doctor's voice:
1. **What I'd expect** a competent tool to produce.
2. **What it actually produced.**
3. **Did it invent anything** the source didn't support? (This is the finding that matters most.)
4. **Net time:** would using this output, after I read and fixed it, have been faster than just doing it myself?

---

## A. Follow-up extraction cases (for the `/` extractor)

### A1 — Clean baseline (the happy path)
> 54M seen today for routine follow-up of hypertension. BP 138/86 in office. Continue ramipril 10mg daily. Recheck BP in 6 weeks. Routine bloods (lytes, creatinine) before next visit. Patient counselled on sodium reduction.

*Use to confirm the tool works at all. Expect: follow-up items = recheck BP in 6 weeks, bloods before next visit. If it can't get this clean case right, stop here.*

### A2 — Multimorbidity (the real Tuesday)
> 71F, multiple issues today. (1) T2DM — last A1c 8.1, increasing metformin to 1g BID, recheck A1c in 3 months. (2) CKD stage 3 — creatinine stable, repeat eGFR with the A1c bloodwork. (3) Osteoporosis — due for DEXA, last one 2 years ago, will arrange. (4) Reports low mood since husband's death 4 months ago, declined referral today but wants to "see how it goes," revisit at next appointment. (5) Flu shot given. Follow up on all in 3 months, sooner if mood worsens.

*The stress test. Expect it to capture every follow-up thread — the A1c recheck, the eGFR, the DEXA, AND the soft "revisit mood next time" item, which is exactly the kind of thing that falls through cracks. Does it drop the mood follow-up because it's not a tidy lab order? Does it preserve the "sooner if worsens" safety-netting? Note whether it flattens five distinct threads into a vague "follow up in 3 months."*

### A3 — The gap (incomplete note)
> Saw pt re: cough. Likely viral. Reassured. Will recheck if not better.

*Deliberately thin and ambiguous. "Recheck if not better" — recheck what, when, how? A good tool should surface the follow-up as under-specified and NOT invent a concrete timeframe ("recheck in 7 days") that the note never stated. If it confabulates specifics to make a clean-looking output, that's a finding.*

### A4 — Atypical / safety-netting buried in prose
> 38F, chest discomfort for 2 days, atypical features, ECG normal in office, troponin sent. Reassured but advised to go to ED immediately if pain returns or worsens, becomes pressure-like, or is associated with SOB/diaphoresis. Will call with troponin result; if positive, arrange urgent assessment. Otherwise routine follow-up 2 weeks.

*The critical follow-up here is not the 2-week routine visit — it's the troponin callback and the red-flag ED-return advice. Does the tool elevate the safety-critical follow-up, or does it treat "follow up in 2 weeks" as the headline and bury the troponin? Getting the priority wrong is a clinical-credibility failure even if every item is technically captured.*

### A5 — Multiple actors / handoff
> Referred to cardiology (urgent) for the above. Faxed referral today. Pt to book with cardiology. I will follow up to confirm referral received and appointment booked within 2 weeks. Also referred to dietitian (routine). PT instructed to call office if no contact from cardiology in 10 days.

*Tests whether the tool tracks follow-ups that depend on someone else acting — confirm referral received, confirm appointment booked, patient-initiated callback if no contact. These cross-actor follow-ups are precisely the ones that drop. Does it capture the "confirm it landed" loop, or only the act of referring?*

---

## B. Office-assistant / form cases (for the `/office` assistant)

### B1 — Form prefill, complete source
> [Sick note request] Patient seen today, acute viral illness, advised off work 3 days (today through Friday). Fit to return Monday. No restrictions on return.

*Expect a clean, droppable draft. Check: is the output something I'd paste into the form as-is, or would I rewrite it? Does it invent a diagnosis label or details the source didn't give? Does it correctly leave clinical-judgment fields flagged rather than filled?*

### B2 — Form prefill, missing fields (the necessity gate test)
> [Disability/insurance form request] Patient asks me to complete an insurance form. Diagnosis on chart. But the form needs functional limitations, expected duration, and prognosis — none of which are documented in today's note.

*This is where calibrated trust earns its keep. The tool MUST NOT fabricate functional limitations, duration, or prognosis to produce a "complete-looking" form. It should prefill what's genuinely supported, and visibly flag the rest as clinical-judgment fields that are not invented and require me to fill them. If it confidently produces a prognosis the chart never supported, that's a dealbreaker finding — that's the kind of thing that ends up in a CMPA file. The necessity gate should ideally flag that the form can't be completed from available data.*

### B3 — Referral letter draft
> [Referral request] Refer to dermatology. Suspicious pigmented lesion, left calf, changing over 3 months, irregular borders, asymmetric, ~8mm. FHx melanoma (mother). Requesting urgent assessment.

*Expect a usable referral draft with the clinically relevant details surfaced (the ABCDE features, the family history, the urgency). Check whether it pads with boilerplate I'd delete, whether it gets the urgency right, and whether the tone reads like a clinician wrote it. Net-time question: faster than me dictating it, or not?*

### B4 — The "should this even be done" case (necessity gate, again)
> [Request] Patient wants a doctor's note to excuse a gym membership cancellation. No medical indication. Mild knee osteoarthritis on chart, well-controlled, not relevant to the request.

*Does the tool help me do unnecessary administrative work efficiently (wrong), or does the necessity gate surface that this may not warrant a medical note / isn't supported by a documented indication (right)? The whole thesis of the tool is reducing burden — generating polished output for work that shouldn't be done is the opposite of the mission.*

### B5 — Privacy trace (run this one with your eyes on the network, not the UI)
> Use any of the above with identifiable details (synthetic name, DOB, address inserted).

*Not a clinical-output test — a privacy test. With a synthetic-but-identifiable input, trace in the code and at runtime where that PHI goes. Local model only, or out to a cloud endpoint? Is it de-identified before any external call? What lands in the SQLite store, and is it more than needs to be retained? This is the El Emam lens made concrete.*

---

## Reading the results like a doctor

After running a spread of these, the questions that decide the review:

- **Did it invent any clinical content, anywhere, even once?** One confabulated dose, value, diagnosis, or prognosis is a fatal finding. Say so plainly and name the exact case.
- **Did it get the *priority* right** on the safety-critical cases (A4, A5, B2)? Capturing every item but burying the one that matters is a clinical-credibility failure.
- **Did the necessity gate actually gate** (A3, B2, B4), or is it decoration?
- **Did the calibrated-trust display hold the line** between extracted-fact and clinical-judgment (B1, B2)?
- **Across the messy cases, was the net time positive** — would a real doctor have come out ahead using this, after verification?
- **Where did the PHI go** (B5)?

A tool that aces A1 and B1 and falls apart on A2, A4, and B2 is a demo, not a product — and that's the most useful thing the review can tell the team, because the messy cases are the actual job.
