# Design — V4 Patient Context Board UI (handoff spec)

Status: **proposed (awaiting approval)**. Not built. Hand to a UI build agent after sign-off.
Aligns to the existing visual language in `frontend/board.html` + `frontend/office.html`
(reuse the `:root` tokens, `.panel`, `.ccard.c-*`, `.item`, `.src`, `.chip`, `.btn`,
`.empty`). Hard product rule, unchanged: **every line restates a FHIR-API fact and cites
its source; no diagnosis/prognosis/interpretation; lean.**

## 1. Information architecture
Two views (V4 §17.1 Screen 1 + §17.2 Screen 2), one page, client-side view switch (keeps it
to one HTML file — lean). No new routes required beyond `/board`.

- **View 1 — Patient Activity List** (default): the inbox. Which patients changed, how much.
- **View 2 — Patient Context Board**: one patient's detail. Reached by activating a row.
- Back affordance: "← All patients" in View 2; focus returns to the originating row.

Rationale: the 7-column activity table needs full width (a left-rail master-detail squeezes
it); the inbox→detail pattern is what clinicians already know (Jakob's law).

## 2. View 1 — Patient Activity List
Full-width `.panel` → a semantic `<table>`.

| Column | Content | Notes |
|---|---|---|
| Patient | name + `id` (mono, faint) | row is the click target |
| New | count | tabular-nums; `--faint` when 0 |
| Updated | count | " |
| Not returned | count | " |
| Open workflow | count | " |
| Last scan | timestamp | relative + absolute on hover |
| Data attention | badge **Low / Medium / High** | derived ONLY from total change volume |

- **Attention badge** — `Low` = `--teal-bg`, `Medium` = `--amber-bg`, `High` = new `--rose-bg`.
  Always **label + icon + color** (never color alone). Copy: "High · data attention".
  Tooltip/`aria-label`: *"Volume of FHIR changes since last scan — not clinical risk."*
  (V4 §17.1 + §23: attention is data/workflow, never disease severity.)
- **Toolbar** (panel header): `Load synthetic scans` / `Re-scan` button + last-scan time.
- **Backing data**: a new `GET /api/fhir/activity` returns per-patient counts (aggregate the
  existing `diff_last_two`); counts MUST match `/api/fhir/diff`.

### States
- **Empty** (no scan): `.empty` with CTA "Load synthetic scans".
- **Single scan**: show patients with all counts `—` + a note "Run a second scan to see changes."
- **Loading**: 3–4 skeleton rows (preserve row height; no spinner-induced shift).
- **Row**: default / hover (`--hair`→bg) / focus-visible (`--focus` outline) / active.

### A11y
- Real `<table>`; `<th scope="col">`; the row is a single `<a>`/`<button>` with
  `aria-label="Open context board for {name}"`. Reading order = DOM = tab order.
- Numeric columns `aria-label` include the noun ("3 new"). Attention not color-only.

## 3. View 2 — Patient Context Board (5 cards, V4 §17.2)
Header: patient name + `← All patients` (ghost btn) + the same attention badge as View 1.
Body: five `.ccard`s, accent per card. Footer: the existing safety restatement line.

1. **Patient Snapshot** — `.c-patient_snapshot` (teal). Demographics, active Conditions,
   current Medications, last visit. Each `.item` with `.src` chip.
2. **New / Updated** — `.c-attention` (amber). Per item: resource + field path, then the
   change as **previous → current** (a `.diff` row: old `--muted`/struck · arrow · new
   `--ink` emphasized); sub-line = the **source API query** (`--mono`, `--faint`).
3. **Open Workflow** — `.c-review_queue` (slate). Open Tasks/items + status + `.src`.
4. **Not Returned & API Limitations** — new `.c-limitations` (`--faint` border). The
   `not_returned` keys + any requested-but-absent resource types, with the honest note
   *"Absent from the API response — reported as not-returned, not deleted."* (V4 §16/§22.)
5. **Source References** — neutral `.ccard`. The full deduped `ResourceType/id` (+ query)
   list — the provenance/audit card.

### States
- **Loading**: skeleton cards. **Empty card**: `.empty` mini ("Nothing to show").
- **Error**: inline `.empty` "Couldn't reach the backend."
- **No scans**: same `no_scans` envelope handling as today.

### A11y
- Cards are `<section aria-labelledby>` with an `<h3>` heading each (landmark structure).
- On open, move focus to the board `<h2>`; on back, restore to the row. Heading hierarchy
  h1(brand) → h2(view) → h3(card).

## 4. Tokens
Reuse everything in `board.html:8-17`. **Two additions (flagged — see §6):**
- `--rose:#9A2B2B; --rose-bg:#F7E4E4` — High data-attention only; always paired with label+icon.
- `.diff` (old/arrow/new) + `.table` styles — composed from existing hairline/spacing/mono
  tokens; **no arbitrary px values**. Reuse the 4/8/12/16 spacing rhythm already in use.

## 5. Build handoff
Inputs for the build agent: this doc + `board.html`/`office.html` as the visual source of
truth + the `GET /api/board/{id}` and (new) `GET /api/fhir/activity` shapes. Build agent:
either ui-senior-guided vanilla-JS (option A) or `react-senior` (option B) per the stack
decision. Then browser-verify with Playwright (3-state: list, detail, empty).

## 6. Stop-rule flags (ui-senior) — confirm before building
- **New semantic color `--rose`** for High attention (the system has teal/amber/slate; this
  adds a fourth). Justified by a 3-level scale needing a distinct top level; paired with
  label+icon so it's not color-only. Confirm.
- **New card style `.c-limitations`** (a 4th `.ccard` accent). Confirm.
No other new design-system surfaces; everything else reuses the current primitives.
