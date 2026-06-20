# COMPASS Judging Lens & Panel Question Bank

This file turns the review's findings into the language the COMPASS panel uses. Read it when filling in the scorecard and the "questions the panel will ask" section. It doubles as pitch preparation. Everything here is drawn from the actual COMPASS *AI in Healthcare Co-Design Event Developer Guide* (June 20, 2026, Invest Ottawa) and verified public sources — not from assumption.

Contents:
1. What COMPASS is
2. The evidence base (real, citable statistics)
3. The six challenge areas (where the tool can sit)
4. Where the experts said to start (Loop is the #1 idea)
5. The four judging criteria (exact framing)
6. The seven design requirements (exact, with the quotes)
7. Synthetic-data rule and prototyping resources
8. The judging panel — who they are and what each will press on
9. What happens after the event
10. Turning findings into the scorecard

---

## 1. What COMPASS is

COMPASS (Consensus On Medical Priorities and AI Solutions in Primary Care) is a multi-phase consensus initiative led by the **University of Ottawa Department of Family Medicine** and **The Ottawa Hospital Department of Family Practice**, with **Bruyère Health Innovation** and **AGI Ventures Canada**. It uses structured sessions with AI experts, primary-care clinicians, and health-system leaders to decide which AI capabilities should be prioritized for primary care. COMPASS is a component of **NAVIGATOR** (Needs-driven AI Vision, Innovation, & Governance Accelerator for Transforming Primary Care).

The guide's central message, in the clinicians' own framing: *they are not asking AI to replace clinical judgement. They want tools that make primary care more doable by reducing repetitive work, supporting preparation and follow-through, and protecting continuity of care.* Every finding in the review should ladder back to that.

## 2. The evidence base (real, citable statistics)

When the review needs a number, use these — they are real and current. Do not invent figures.

- The guide's own framing: family physicians lose **roughly 19 hours per week** to administrative work, **over half report burnout**, and **nearly one in five Canadians has no regular primary-care provider**.
- **CMA & CFIB, *Losing doctors to desk work* (Jan 2026)**, National Survey on Administrative Burden, n=1,924: physicians spend on average **~9 hours/week** on admin (nearly one-fifth of total working time) = **~42.7 million hours/year** nationally; **47% is unnecessary** = **~19.8 million hours**, equal to **9,093 full-time physicians (~9% of the workforce)**. Per physician, that's up to **~199 hours/year** reclaimable — more than a full month of work.
- Well-being (same report): **93%** say paperwork disrupts work-life balance, **95%** say it reduces professional fulfillment, **~9 in 10** link it to burnout; **>50%** plan to reduce hours, **1 in 4** are considering early retirement.
- Top sources of unnecessary work: health-system processes (**85%**), insurance companies (**76%**), government forms (**59%**), pharmacies (**58%**), EMR systems (**51%**). **Family physicians are more burdened than other specialists.**
- **CFIB, *Patients before Paperwork* (2023)**, Nova Scotia benchmark: ~**18.5 million hours** of unnecessary admin nationally; physicians spent **10.6 hours/week** on admin, **38% unnecessary**.

Source documents are in the research archive (`00_Source_Materials/`) and public at cfib-fcei.ca and cma.ca. The point these make for the review: administrative burden is a **measured clinical-capacity loss and a documented burnout driver**, not a paperwork annoyance — so a tool that credibly returns physician time is addressing a top-tier problem.

## 3. The six challenge areas (where the tool can sit)

Identify which of these the tool targets, then judge it against how that work *actually* happens. (Loop targets #5 and #4; the Patient Context Board alternative targets #1 and #6.)

1. **Pre-visit preparation** — chart scan for what's due/overdue, summary of what changed since last visit, dynamic pre-visit questionnaires, patient-facing check-in.
2. **Encounter support & point-of-care reasoning** — guideline-based prompts in-visit, smart search across scanned docs/faxes, community-resource retrieval, whole-problem-list summaries. *Explicitly "well beyond ambient documentation."*
3. **Medication & prescribing support** — polypharmacy/deprescribing, monitoring reminders for high-risk drugs, limited-use code reminders, drug-shortage alerts, pharmacy cost/coverage checks, cross-setting med reconciliation.
4. **Follow-up & care-plan automation** — auto follow-up task generation from visit notes, test-completion tracking with alerts for results that haven't returned, patient reminders tied to care-plan milestones, complex care-plan scaffolding for multimorbidity. *Described as "a major source of risk and frustration" because nothing reliably converts visit decisions into downstream actions.*
5. **Administrative & coordination automation** — inbox/fax triage (classify, dedupe, route, summarize), referral intelligence (availability, wait times, scope matching, auto-resubmission of rejected referrals), forms automation (auto-populate insurance/disability/school forms from chart data), billing/roster reconciliation, after-hours triage. *"Consistently identified as where AI should start."*
6. **Continuity & whole-person intelligence** — longitudinal narrative summaries, family-relationship visualization, social/community context, continuity handoff for covering physicians.

## 4. Where the experts said to start (Loop is the #1 idea)

In a separate session, nine healthcare-AI experts independently ranked near-term project ideas. The top picks:

1. **Digital medical office assistant** — "Understands and completes common paperwork, referral packages, scheduling, and medication reviews with **structured, auditable outputs**."
2. Inbox manager — ingests EMR messages, dedupes, auto-tags/triages, summarizes threads with proposed actions.
3. Ambient scribe + micro-prompts — structured documentation plus brief nonintrusive prompts.
4. (tie) Pharmacy agent — coverage checks, pharmacy clarification loops, refills, interaction checks.
4. (tie) Validated triage & self-management — patient-facing acuity routing with safety nets.

**This matters for the review and the pitch:** Loop's `/office` digital office assistant *is* the experts' #1-ranked idea, and its `/` follow-up extractor sits squarely in challenge area #4. The team isn't guessing at a problem — it's building the convergent top priority. Say so in the verdict. (The guide also notes these are "convergence points, not constraints" — being the #1 idea is validation, but it raises the bar: the judges have thought hard about this exact tool.)

A useful framing the workflow judge has used publicly: the field is moving **"beyond the AI scribe"** to the next wave of primary-care AI. Loop is explicitly post-scribe — admin automation and follow-through, not documentation. That's the right side of where the experts are looking.

## 5. The four judging criteria (exact framing)

Prototypes are scored by a clinician panel across four dimensions. Use this exact framing in the scorecard.

1. **Clinical importance** — *does it address a real, high-frequency problem?*
2. **Technical feasibility** — *could it realistically be built and deployed within 6–12 months?*
3. **Safety and privacy** — *what is the risk profile and what governance would it need?*
4. **Workflow fit** — *how likely is it to integrate into existing primary-care workflows without adding burden?*

The guide's own tie-breaker, worth quoting in the verdict if relevant: *"A working prototype with synthetic data and a credible integration story will score higher than a polished front-end with no clinical logic."* Clinical logic + integration story beats UI polish.

## 6. The seven design requirements (exact, with the quotes)

These emerged repeatedly across expert and clinician sessions. Check each explicitly — a violation is automatically high-severity, because the panel treats them as table stakes. (Note: there are **seven**, not four — integration, low cognitive burden, and proactivity are easy to forget.)

1. **Integration over fragmentation** — no new standalone app, no new login. Fewer clicks, tabs, subscriptions. *"If we end up with 20 different tools and 20 more logins, we've failed."*
2. **Low cognitive burden** — outputs concise and timely; include a *"don't interrupt me now"* control so the clinician governs when AI communicates. *Relevance filtering matters more than comprehensiveness.*
3. **Actionable outputs** — don't just generate text; convert decisions into tasks — draft the referral, queue the follow-up, prepare the form. *"The gap between information and action is where care falls through the cracks."*
4. **Calibrated trust** — transparent about confidence and limitations; let the clinician audit, edit, override; show reasoning. *Augment judgement, don't bypass it.*
5. **Proactive, not reactive** — anticipate needs before and after the visit; flag what's due, track what's pending, remind what's unfinished — rather than waiting to be asked.
6. **Practical affordability** — small clinics run on tight margins; be realistic about cost. *Expensive infrastructure or per-seat licensing is an immediate adoption barrier.*
7. **Privacy by design** — event materials are synthetic only, but design ahead for real PHI: data minimization, local processing, clear governance from the start.

## 7. Synthetic-data rule and prototyping resources

All event prototyping must use **synthetic or de-identified data only — no real patient data, no live EMR connections.** The review's test material must respect this (see `clinical-test-scenarios.md`). The guide's recommended open resources, useful both for building and for grounding the review's test cases:

- **Synthea** (MITRE) — synthetic FHIR R4 / C-CDA / CSV patient records with conditions, encounters, meds, observations, care plans. Pre-built 100- and 1,000-patient sets. Best for anything needing patient timelines or structured records.
- **MTSamples** — 5,000+ public-domain medical transcription samples (SOAP/progress/office notes across 40 specialties). Best for clinical-note summarization, extraction, and inbox-triage prototypes — i.e., realistic raw input for Loop's follow-up extractor.
- **MIMIC-IV** (de-identified, hospital/ICU) — clinical notes, meds, labs; demo subset open.
- **Health Canada DPD** and **CCDD** — Canadian drug reference / standardized drug terminology.
- **HAPI FHIR (R4)** and **SMART on FHIR Sandbox** — open FHIR servers for a credible integration story. **CDS Hooks** for in-EHR prompt triggering.

Awareness of HL7 FHIR (R4), CDS Hooks, and SMART on FHIR strengthens the integration story the judges score under workflow fit, even without full implementation.

## 8. The judging panel — who they are and what each will press on

Per the organizers' own announcement, the attending physicians, judges, and mentors for this event include the people below. (Treat this as the known roster; confirm the final panel on the day. The lenses hold regardless of exact composition.) Build the "questions the panel will ask" section around this mix.

- **Dr. Arun Radhakrishnan** — Tier 2 Clinical Research Chair in **Primary Care AI, Innovation and Implementation** (uOttawa); family physician; clinical research lead, TOH DFP; Bruyère investigator; deeply tied to the **Champlain BASE eConsult** service (a landmark real-world primary-care workflow tool: median ~0.9-day specialist response, ~two-thirds of cases resolved without a face-to-face visit). **His lens: implementation and workflow fit.** Expect: *Where does this sit in the existing workflow and relative to the EMR? How many extra steps per patient? What's the adoption path? Have you tested it on messy real cases, not just the demo? What's the net time saved after verification?* He has publicly framed the field as moving "beyond the AI scribe" — be ready to say why Loop is the right next step.

- **Dr. Khaled El Emam** — Tier 1 Canada Research Chair in **Medical AI** (uOttawa); Director of OMARI and the Electronic Health Information Laboratory; world authority on **de-identification, re-identification risk, and synthetic-data generation**; **Privacy-by-Design Ambassador** recognized by the Ontario IPC; Scholar-in-Residence at the IPC. **His lens: privacy and governance.** Expect: *Trace exactly where the PHI goes — prove "local" in the code. How is identifiable data handled before any processing that could expose it? What's the re-identification risk on what you retain? What's stored, how long, why (the SQLite schema is the honest answer)? If you lean on synthetic data, how do you know it's actually safe — synthetic data can leak. Would this pass PHIPA and a privacy officer?* He will not accept hand-waving; a rigorous privacy-by-design story is worth real points with him, and a vague one loses them fast.

- **Dr. Sharon Johnston** — Scientific Director, Institut du Savoir Montfort; family physician / health-services researcher. **Lens: health-system fit, primary-care delivery, equity** (including Franco-Ontarian and underserved populations). Expect: *Who does this help and who might it leave behind? Does it fit team-based primary care, not just the solo physician? How does it perform across diverse patients?*

- **Dr. William Hogg** — Acting Chair, DFM uOttawa; senior Canadian primary-care researcher. **Lens: evidence and practice transformation.** Expect: *What's the evaluation plan? How would you measure that it actually reduces burden? What's the evidence this works rather than the assumption?*

- **Dr. Douglas Archibald** — Director of Research and Innovation, DFM uOttawa. **Lens: research rigor and evaluation.** Expect: *How do you know it's accurate? What's your error rate, and how did you measure it?*

- **Kevin Haaland** — CEO, Cliniconex (clinic communication/automation company). **Lens: commercial viability and deployment.** Expect: *What does it cost to run and maintain? What's the realistic path into clinics? Who pays?*

- **Dr. Sara Mousa** — family-medicine resident. **Lens: frontline usability.** Expect: *Would a working physician actually open this on a busy day? Is it obvious to use without training?*

For each likely question, the review should state honestly whether the current build can answer it **confidently, partially, or not yet.** That honesty is itself worth points — the guide explicitly values knowing your tool's limits over a flawless-demo posture.

## 9. What happens after the event

This is not a one-day exercise. The most promising concepts are prioritized for **follow-on development and potential piloting in real clinical settings** through the Bruyère Health Research Institute and uOttawa DFM. It's "the entry point to a pipeline that can take strong ideas into clinical testing." Useful framing for the verdict: the review isn't grading a hackathon toy, it's pressure-testing a candidate for a real pilot — so the bar is "could this survive a clinic," not "did it demo well."

## 10. Turning findings into the scorecard

For each of the four criteria, give a plain read — **strong / mixed / weak** — and one line of justification grounded in what you actually saw using the tool. Resist grade inflation: the value to the team is an accurate read they can act on before the real panel does it for them. A "mixed" with a clear reason is more useful than a reflexive "strong."

If a fatal finding exists (confabulated clinical content, PHI leaving the box, net-negative time, a violated design requirement), the relevant criterion cannot be "strong" no matter how polished the rest is — and the top-line verdict should say plainly that the tool isn't yet panel-ready on that axis.
