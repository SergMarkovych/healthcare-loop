---
status: first-version
created: 2026-06-20
sources: 26 primary/secondary (deep-research harness, 5 search angles)
caveat: adversarial verification phase hit a session token limit; treat figures as sourced literature signals, not individually re-verified facts
---

# AI tasks — research-backed first version

Evidence base for the 6 AI touchpoints in Loop. Each finding is tagged with a source.
Numbers are **as reported by the cited paper** — the harness's per-claim re-verification
was cut short by a token limit, so weight them as literature signal, not gospel.

## Cross-cutting findings (apply to every task)

| # | Finding | Source | Implication for Loop |
|---|---|---|---|
| X1 | Few-shot helps **most** clinical NLP tasks, but zero-shot wins on **some** (medication-attribute extraction, sense disambiguation). Optimal strategy is **task-dependent**. *(3-0 confirmed)* | JMIR Med Inform e55318; PMC11036183 | Don't blanket-adopt few-shot. Pick per task; test. |
| X2 | For **classification/triage**, **heuristic (structured task-description) or prefix prompts are optimal — NOT chain-of-thought**. | PMC11036183 | Necessity gate (task 3) should use a structured prompt, not CoT. |
| X3 | Structured-output failures are mostly **formatting, not comprehension** — Llama wraps JSON in fences/prose where GPT returns clean. | arXiv 2601.06151 | Keep schema enforcement + validate-and-retry (already present in `llm.py`). |
| X4 | **Cross-model prompt portability is poor** (F1 swings 0.4–0.6 across model families). | arXiv 2601.06151 | A prompt tuned on GPT-4 ≠ works on llama3.1/qwen2.5. Tune for the deployed model. |
| X5 | Model-size floor: **14B** (Qwen2.5-14B, Phi-4-14B) viable for clinical extraction at 4-bit/12GB; **3B fails**. 8B (llama3.1) is borderline. | JAMIA Open ooaf109 | Prefer qwen2.5-14B over llama3.1-8B if hardware allows. |
| X6 | **Quantization is not free**: 4-bit drops MedMCQA ~4%, collapses PubMedQA 43.9%→22.4%. | ACL 2024.findings-acl.348 | Avoid aggressive 4-bit for reasoning-heavy fields (task 5). |
| X7 | **Negation hallucination** (model inverts a clinical fact) = 30% of all hallucinations, the most dangerous subtype; CoT atomisation **increased** summarization errors. | Nature Dig Med s41746-025-01670-7 | Fail-safe summarizer design is validated. Don't add CoT to summarization. |
| X8 | Medication-safety review: only **46.9% fully correct** even at 100% sensitivity; **contextual-reasoning failures outnumber factual hallucinations 6:1**. Dominant failure = not individualizing to patient context. | arXiv 2512.21127 | Anything judgment-laden (tasks 3, 5) MUST keep physician-in-the-loop. |

## Per-task reading

### Task 1 — Encounter extraction (`backend/llm.py`)
- **Prompt style:** heuristic/structured task description + JSON schema enforcement + validate-and-retry. Loop already does all three (`llm.py:65-90`, Ollama `format=schema`).
- **Few-shot:** add examples, but **per-field** — some fields extract better zero-shot (X1). The handcrafted `mock.py:_CANNED["sample-1"]` is a ready few-shot exemplar.
- **Confidence:** models are overconfident; the **evidence-snippet requirement is the real guardrail** (forces grounding). Keep it mandatory.
- **Top risk:** negation inversion (X7) — "no chest pain" → "chest pain". A verbatim-evidence requirement partly defends this.

### Task 2 — Board summarization (`backend/fhir/summarize.py`)
- Deterministic-default + forbidden-word filter is **well-supported** by X7 (summarization is where negation hallucination bites; CoT made it worse).
- A **positive-framing template** can lift prose quality, but the safety filter must stay as the backstop. **Do not add CoT.**

### Task 3 — Necessity / triage gate (`backend/office/necessity.py`)
- Classification task → **heuristic/prefix prompt, low temperature, structured route definitions** (X2). NOT CoT.
- The current 8 hardcoded rules are defensible for **known** categories; an LLM should only handle the **unknown/free-text** tail, with a **conservative fall-back to `physician_review`** on low confidence (X8: contextual reasoning is the weak spot).

### Task 4 — Referral intelligence (`backend/office/referral_intel.py`)
- Split the problem: **LLM for the fuzzy reason→specialty match**; **deterministic rules for rejection-risk** from directory metadata. The model must **not invent** risk scores — directory stays ground truth.

### Task 5 — Clinical field draft generation (`backend/office/forms.py`) — HIGHEST RISK
- X8 is the headline: 46.9% correctness, contextual failures dominate. Drafting functional-limitations / prognosis / work-capacity is exactly the "individualize to context" task LLMs fail.
- **Guardrails (all mandatory):** every drafted field carries an **evidence snippet + confidence**; physician must **explicitly accept**; **never auto-commit** a clinical-judgment field. This *extends* — does not weaken — Loop's existing "flag, never invent" stance.

### Task 6 — Patient instructions & safety netting (`backend/llm.py` / `schema.py`)
- Target **grade 6–8**, validated **deterministically post-generation** (Flesch-Kincaid), not by asking the model to self-grade.
- Require **≥1 red-flag per active problem**; template the safety-netting structure. Keep physician review (generation hallucination risk).
- *(Plain-language angle returned sources but several specific claims were truncated by the token limit — flag for a re-run if this task is prioritized.)*

## Model recommendation
- **qwen2.5-14B or Phi-4-14B > llama3.1-8B** for extraction if 12GB+ VRAM (X5).
- Avoid aggressive 4-bit quant on reasoning-heavy tasks 3/5 (X6).
- Domain-tuned models (MedGemma/Meditron, per the landscape blog) are optional — a strong general instruct model often matches them on **structured extraction**.

## Sources (26)
Primary: medinform.jmir.org/2024/1/e55318 · arxiv 2505.08704 · medinform.jmir.org/2025/1/e78432 ·
academic.oup.com/jamiaopen ooaf109 · arxiv 2411.10020 · arxiv 2601.06151 · PMC11036183 ·
aclanthology 2024.findings-acl.348 · nature s41746-025-01670-7 · arxiv 2512.21127 · PMC12540348 ·
arxiv 2510.02463 · arxiv 2503.05701 · formative.jmir.org/2025/1/e80917 · PMC11554522 ·
jmir.org/2025/1/e69955 · PMC10811715. Secondary: arxiv 2510.17764 · arxiv 2502.15871 · arxiv 2605.15680 · PMC12099328.
(Full list + claim counts in the workflow output.)
