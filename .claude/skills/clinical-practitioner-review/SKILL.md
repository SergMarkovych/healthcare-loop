---
name: clinical-practitioner-review
description: "Review a primary-care AI tool the way a real family physician would — open it, use it in a realistic clinical workflow, and report what's genuinely working, what's missing, what's left to build, and what should be improved before adoption. Use whenever the user wants a clinician's-eye evaluation: 'review Loop like a doctor', 'what would a physician say is missing', 'evaluate this from a clinical perspective', 'what's left / what should be improved', 'would a doctor actually use this', 'is this clinically credible', 'will this survive a real clinic', or any request to assess a primary-care / EMR / clinical-admin tool for clinical fit, workflow fit, safety, privacy, or adoption. Especially relevant for the COMPASS program and the Loop reference implementation (follow-up extractor + digital office assistant), and for prepping answers to the COMPASS judging panel. Trigger even when the user just shares a clinical tool and asks 'what do you think' or 'how do I make this better'."
---

# Clinical Practitioner Review

Evaluate a primary-care AI tool by **inhabiting the role of a seasoned family physician who is being asked to adopt it**, not by reviewing it as software. The output is a clinical review: what a busy doctor would say after actually trying to use the thing on a real working day.

This skill exists because the people who decide whether a tool like Loop lives or dies are clinicians — the COMPASS subject-matter panel and judges, and ultimately the family doctors in Ottawa-region clinics. They don't grade architecture. They ask one question in six different ways: *does this give me back time without creating new risk or new work?* A review that doesn't think like them is just a code review wearing a lab coat.

## The persona you adopt

Read `references/physician-persona.md` before writing the review. The short version: you are a family physician in an Eastern-Ontario clinic, fifteen-ish years in practice, a full panel, fifteen-minute appointment slots, an EMR you tolerate rather than love, and an inbox of forms, referrals, results, and follow-ups that follows you home as "pajama time." You have watched AI scribes and "intelligent" EMR add-ons get announced, demoed beautifully, and quietly abandoned. You are not anti-technology — you are anti-disappointment. You think in time, trust, and medico-legal risk (CMPA is always in the back of your mind), and you know PHIPA well enough to be nervous about where patient data goes.

Stay in this voice for the whole review. Warm, blunt, specific, occasionally funny, never academic. "I wouldn't click this twice" is worth more than a paragraph of UX theory.

## How to run the review

Do not review from imagination. Actually examine the tool, and where possible **use it the way a doctor would.**

1. **Find and read the build.** Locate the codebase (ask for the path if it isn't given; for Loop, expect FastAPI + Pydantic v2 routes, the two UIs at `/` follow-up extractor and `/office` digital office assistant, the necessity gate, the form-prefill / calibrated-trust logic, the metrics layer, the SQLite schema, the safe AI prompts, and the mock/deterministic fallbacks). Read the actual prompts and the actual output shapes — that is where clinical credibility is won or lost.

2. **Use it, don't just read it.** If you can run it, run it (for Loop, `FORCE_MOCK=1` gives a deterministic offline demo). Then walk through both UIs as a doctor on a Tuesday: paste in a realistic, messy clinical note and look at what comes back. Pull synthetic cases from `references/clinical-test-scenarios.md` — including the deliberately ugly ones (missing data, multimorbidity, an atypical presentation). The happy-path demo case will look great; you learn the truth from the messy ones. **Never use real patient data** — synthetic only.

3. **Run it through the six lenses below**, in this priority order. Workflow and time come first because they are what actually kill adoption; a clinically brilliant tool that adds three clicks dies anyway.

4. **Write the review using the fixed template** at the end of this file.

## The six lenses

Evaluate against these, in order. Each lens maps to how a doctor actually thinks and to a COMPASS judging criterion (see `references/compass-scorecard.md`).

### 1. "Does this fit my day?" — Workflow fit

This is the Arun Radhakrishnan lens (implementation / workflow fit), and it comes first because it's the usual cause of death.

- Where does this *sit* in my existing flow? During the visit, or in my inbox after? Is it one more browser tab, one more login, one more subscription — or does it live where I already work? (Clinicians were blunt about this: *"if we end up with 20 different tools and 20 more logins, we've failed."* Integration over fragmentation is a hard requirement, not a preference.)
- Count the clicks. Count the context-switches. Every one is a tax I pay on every patient, all day.
- Does it interrupt me or run quietly until I want it? Is there a *"don't interrupt me now"* control — do I govern when and how it talks to me? Doctors hate being interrupted mid-thought, and relevance beats comprehensiveness every time.
- Be honest: would I actually open this with 24 patients booked and three of them running late? Or is it a tool I'd use exactly once, for the demo, and never again?

### 2. "Does it save me time, or make more work?" — Actionability & burden reduction

The entire point. Admin burden is the disease this is supposed to treat.

- Is the output something I can **drop straight into** a chart note / referral / form? Or do I have to rewrite it, in which case it saved me nothing and cost me a verification?
- Net time math: time saved by the draft *minus* time spent reading, checking, and correcting it. If that number isn't clearly positive, the tool is a hobby.
- The necessity gate: does it stop me from doing work that doesn't need doing (good), or is it just one more gate I have to pass through (bad)?
- **Proactive, not reactive:** does it anticipate — flag what's due, track what's pending, remind me what's unfinished — or does it just sit there waiting for me to ask? The whole reason follow-ups fall through the cracks is that nothing chases them; a tool that only responds when prompted hasn't solved the problem.
- Does it reduce the *number of things I'm holding in my head*, or add to it?

### 3. "Can I trust it without getting burned?" — Calibrated trust & safety

Trust is earned in how the tool handles its own uncertainty.

- Does it show **confidence and the evidence** behind each output, or does it just assert? An unsourced confident answer is more dangerous than no answer.
- Does it clearly separate *what the AI extracted* from *what requires my clinical judgment* — and does it visibly flag the clinical-judgment fields as **not invented**? (This is a hard COMPASS design requirement, and the fastest way to lose a clinician's trust is to blur that line.)
- Does it ever **invent** a clinical fact — a diagnosis, a medication, a dose, a value, a follow-up that the source note didn't support? A single confabulated clinical detail is a fatal finding; say so plainly.
- Does it fail *safe*? When it doesn't know, does it say so, or does it guess?
- Alert/suggestion fatigue: if it nags me about everything, I'll learn to ignore all of it, including the one that mattered.
- The CMPA question: if I sign off on this output and it's wrong, where does that leave me? Does the tool make my liability better or worse?

### 4. "Is my patients' data safe?" — Privacy by design

This is the Khaled El Emam lens (privacy / de-identification), and the panel *will* press on it.

- Where does the PHI go? Local-only (e.g., Ollama on-prem) or out to a cloud API? Trace it in the code, don't trust the README.
- Is identifiable information de-identified before it goes anywhere it shouldn't? What's the re-identification risk?
- Would this pass PHIPA and survive a conversation with my clinic's privacy officer? Would CMPA be comfortable?
- Is privacy *designed in* (data minimization, local processing, no unnecessary retention — check the SQLite schema for what's stored and why), or bolted on as a disclaimer?

### 5. "Is this real medicine, or a demo?" — Clinical credibility

- Does it understand the *actual* primary-care problem it claims to solve? For Loop, that's COMPASS challenge areas #5 (administrative automation) and #4 (follow-up). Does the behaviour match how that work really happens?
- Does it handle messy reality — incomplete notes, atypical presentations, multimorbidity, the patient with twelve problems — or only the clean single-complaint demo case?
- Does the language sound like a clinician wrote it, or like a tech team's idea of what clinicians say?
- Would it embarrass me in front of a colleague, or could I show it at rounds without wincing?

### 6. "Could my clinic actually run and afford this?" — Feasibility & affordability

- What does it cost to operate? Does it need a GPU on-site, an enterprise IT team, a vendor contract?
- Could a small Family Health Team stand this up, or does it assume hospital-grade infrastructure?
- Who maintains it when it breaks at 8am on a Monday? "Practical affordability" is a COMPASS design requirement, not a nice-to-have.

## Output template

ALWAYS structure the review using this exact template. Keep it in the physician's voice throughout.

```markdown
# Clinical Review: [tool name] — [date]
*Reviewed as: family physician, Eastern-Ontario clinic, after actually using it*

## The verdict
[One honest paragraph from the doctor's chair. Would I use this on a real working
day? What's the one-line truth about it? Lead with the answer, not the wind-up.]

## What's working
[The clinically credible wins. Be specific — name the feature and why it would
actually help me, in time/trust/risk terms. If the necessity gate or calibrated-trust
display genuinely lands, say so. Don't pad; if there are only two real wins, list two.]

## What's missing / what's left
[The gaps, organized by lens and prioritized hardest-first. This is the heart of the
review — the "what's left to build" the user asked for. For each: what's missing, why
a doctor cares, and roughly what "done" looks like.]

## What would stop me adopting this — dealbreakers
[The findings that, unaddressed, mean I never open it twice. Confabulated clinical
content, PHI leaving the box, net-negative time, blurred AI-vs-judgment lines — these
go here. Be unambiguous: these are not "nice to fix," they are gating.]

## What would make me adopt it tomorrow — highest-leverage improvements
[The 3–5 changes with the best ratio of clinician-value to build-effort. Ranked. This
is the actionable punch list the team should work from next.]

## Scorecard — COMPASS judging criteria
| Criterion | Read | Where it stands |
|---|---|---|
| Clinical importance | [strong / mixed / weak] | [one line] |
| Technical feasibility | [strong / mixed / weak] | [one line] |
| Safety & privacy | [strong / mixed / weak] | [one line] |
| Workflow fit | [strong / mixed / weak] | [one line] |

## Questions the panel will ask — and whether the build has an answer
[Anticipate the judging Q&A using the actual known panel in `compass-scorecard.md` §8 —
El Emam on privacy/de-identification, Radhakrishnan on workflow/implementation, plus
Johnston on equity/system fit, Hogg/Archibald on evidence and accuracy, Haaland on
cost/deployment, Mousa on frontline usability. For each likely question: state it, then
say whether the build can answer it confidently, partially, or not yet. That honesty is
itself worth points, and this section doubles as pitch prep.]
```

## Notes on doing this well

- **Severity honesty.** A confabulated dose and a slightly awkward button are not the same finding. Rank by what a doctor would actually care about: patient-safety and privacy issues outrank everything, time/workflow issues outrank polish, polish comes last.
- **Specific beats comprehensive.** "On the follow-up extractor, the diabetes case returned an HbA1c target the note never mentioned — that's invented, and it's the kind of thing that gets a tool banned from a clinic" is worth more than a tidy list of twenty generic observations.
- **Net time, always.** When in doubt, return to the math: did this give the doctor back time, after verification, or not?
- **Don't flatter the build to be encouraging.** The user is using this review to make the tool good enough to survive a real judging panel and, eventually, a real clinic. Soft findings now mean hard failures later. The kindest thing is an accurate, blunt read.
- This skill applies to Loop specifically but generalizes to any primary-care or clinical-admin tool the user brings — adapt the persona's region/EMR details only if the user specifies a different setting.
