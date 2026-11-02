# Vox usage-fix v1 — Design Spec

**Date:** 2026-06-14
**Basis:** The three P1 findings that survived Opus, `isMeta`-aware re-validation in
[`docs/2026-06-14-vox-usage-findings.md`](../../2026-06-14-vox-usage-findings.md) (A5, A7, A14).
No P0s survived; the P2s are explicitly out of scope (listed below).

**Goal:** Close the three verified quality gaps that cost real users a good answer in the
06-07→06-14 usage corpus: (A7) gosom review-volume corruption, (A5) aggregator prices
presented as bookable, and (A14) a silently-backgrounded browser agent self-stopped on a
false stall.

**Packaging:** One spec (this doc) → one implementation plan with three task groups:
**A7** (maps-cli Python, TDD) · **A5** (vox / vox-browser prose) · **A14** (vox / vox-browser
prose).

---

## Section A7 — gosom review-volume: scraper-level flag + per-finalist re-fetch

### Problem
gosom's list-card `review_count` returns `0`/`null` under some Google DOM variants for a place
that *has* reviews (corpus evidence: Tompkins **860 vs 0**, Zucker's **463 vs 0 vs 0** on
repeat fetches; `e97e2e8b:325/341`). `maps_cli/normalize.py:14,29` passes that value straight
through, so a misleading `0` reaches the rating×volume ranking signal. Separately, a finalist's
volume mutated **5,526→462** across a session resume (`9458b053`) — an orchestrator-side
carryover, not a scraper divergence.

### Data-contract change (`maps_cli/normalize.py`)
Add a status field and null out the misleading zero. The output contract gains
`reviewCountStatus`:

| `raw["review_count"]` | `reviewCount` (out) | `reviewCountStatus` (out) |
|---|---|---|
| a positive int (e.g. `460`) | `460` | `"ok"` |
| `0` | `null` | `"unavailable"` |
| `None` / missing | `null` | `"unavailable"` |

- Applies in both `normalize_place` and `_brief` (so `alternatives[]` carry the status too).
- A small helper, e.g. `_review_fields(raw) -> {"reviewCount", "reviewCountStatus"}`, keeps it DRY.
- `matcher.py` is unaffected — it sorts on the **raw** gosom dict (`sr[1].get("review_count")
  or 0`), not the normalized output, so its tie-break behavior is unchanged.

### Per-finalist re-fetch (`maps_cli/commands/places.py` + a seam in `gosom.py`)
When the matched record's volume is missing, do **one** extra gosom run to recover it, then
re-match. New orchestration in the `places` command path (extract to a testable function, e.g.
`resolve_with_volume(name, near, search, n, timeout) -> record`):

1. Run the primary query exactly as today (`{search} {near}` if `--search` else `{name} {near}`),
   match, normalize.
2. If `reviewCountStatus == "unavailable"` on the match, pick a **broad fallback term** that
   differs from the primary query to land a different DOM variant, in priority order:
   1. the matched record's `category` (this is what `--search` is *for*),
   2. else, if the primary used the exact name, the original `--search` term if any,
   3. else skip the re-fetch (nothing better to try).
   Re-run gosom once: `{fallback_term} {near}`, `depth=1`, same `timeout`. **Never** re-fetch by
   exact name alone — that is the single-page anti-bot trap the `--search` flag exists to dodge.
3. Re-match the re-fetch rows by `name`. If the re-matched record has a real volume
   (`review_count > 0`), **merge only the recovered `review_count` (and `review_rating` if the
   primary lacked it)** into the primary record — keep the primary's address/hours/link, which
   were already good. Re-normalize.
4. Still missing after the re-fetch → leave `reviewCountStatus: "unavailable"`.

Bounded cost: at most one extra gosom run per `places` call, same 90s timeout. (`run_gosom`'s
existing empty-result retry is orthogonal and unchanged.)

### Renderer (`maps_cli/commands/places.py`)
`PLACE_COLUMNS` "Rating×Reviews" cell renders `f"{rating}×⚠"` when
`reviewCountStatus == "unavailable"`, else `f"{rating}×{reviewCount}"`. No misleading `×0`.

### Playbook prose
- **`vox-maps/SKILL.md`** (line ~28): the subagent consumes the structured
  `reviewCountStatus` (`"unavailable"` → `⚠ volume-UNAVAILABLE`, never "0 reviews"), and notes
  maps-cli now auto-re-fetches once before reporting unavailable.
- **`vox/SKILL.md`** Places tier: **carry-forward rule** — once a finalist's review volume is
  resolved in a run, reuse that reconciled number across session resumes / follow-ups; never
  let a finalist's volume silently change between turns (the 5,526→462 bug).

### Tests (TDD, `maps-cli` pytest)
- `normalize_place`/`_brief`: `review_count` of `460` → `(460, "ok")`; `0` → `(null,
  "unavailable")`; missing → `(null, "unavailable")`; alternatives carry status.
- `resolve_with_volume` with a **fake gosom** (monkeypatched `run_gosom`): returns `0` on the
  primary then `463` on the category re-fetch → final record `reviewCount=463, status="ok"`;
  returns `0` on both → `status="unavailable"` and exactly two gosom calls; primary already
  `>0` → exactly one gosom call (no re-fetch).
- `places` command (existing renderer test seam): unavailable → cell shows `×⚠`; recovered →
  cell shows the number.

---

## Section A5 — brand-engine availability/price verification (top-3, bookable inventory)

### Problem
For lodging, vox presented Google-Hotels aggregator prices (DoubleTree LIC $189, Hyatt Place
LIC $203) as recommended **bookable** picks with only a soft "rates can move" hedge
(`e4dbd299:949/951/957`). Brand-site truth: Hyatt Place LIC was "Hotel Not Available" and
DoubleTree's real rate was $259/$239 (`:1218/:1044`) — caught only reactively after user
pushback.

### Behavior (`vox/SKILL.md`, Places & browser tier)
Add a **bookable-inventory verification** rule:

- **Trigger:** the query is bookable-inventory — lodging/housing intent keywords (hotel, motel,
  inn, room, stay, lodge, Airbnb/short-term rental, apartment, rental, lease, sublet) — **and**
  the answer will present a specific price/availability as actionable.
- **Action (Wave 2):** dispatch the single `vox-browser` agent to verify the **top 3 finalists'**
  current availability + price on the **brand booking engine** (the hotel's own site, or the
  platform that actually takes the booking) **before** ranking them as bookable. These three
  checks run **serially** through the one browser agent (accepted wall-cost).
- **Aggregator status:** Google Hotels / Booking / Kayak snippet prices are **availability
  signals only** until brand-verified; they may rank candidates but may not be presented as
  "book this at $X."
- **Degrade (no Chrome):** present aggregator prices with a `⚠ unverified — aggregator price,
  confirm on the brand site` tag, never as a bookable instruction. Honest degrade, not a halt
  (consistent with the existing `--web-fallback` posture).

### Browser playbook (`vox-browser/SKILL.md`)
Add a **brand-engine availability check**: given a finalist name + dates, navigate the brand
booking engine, read the live nightly rate + availability, and return
`{available: bool, rate, url}`. Handle the sold-out / "no rooms" state explicitly (return
`available: false`), and never infer availability from an aggregator tab.

### Honesty gate (`vox/SKILL.md` step 7 + `references/output-template.md`)
A bookable pick carries a verification tag: **brand-verified ✓** (rate + availability confirmed
on the brand engine) or **aggregator-only ⚠** (price is a signal, not confirmed bookable).

### Verification (manual / live-rigor)
No unit tests (prose behavior). Validate with `tools/validate_skills.py skills` (skills still
parse) and a live-rigor spot check on a lodging query in a follow-up session.

---

## Section A14 — background browser narration, no false-stall self-stop

### Problem
vox silently dispatched a background browser agent (`e4dbd299:533/538`), then **self-stopped a
correctly-working agent** via `TaskStop` (`:570`) on a stall it inferred from a quiet period —
admitting *"it wasn't actually frozen … My mistake was launching it in the background so you
got no narration"* (`:576`). (Re-validation correction: this was vox stopping its own agent,
**not** a user ESC.)

### Behavior (`vox/SKILL.md`, browser tier)
- **Narrate at launch:** when dispatching the single browser agent in the **background**,
  announce what it's doing, which finalists it will visit, and that **Chrome will move on its
  own** and **quiet 30–60s gaps between clicks are normal, not a hang**.
- **Never self-stop on an inferred stall:** do not `TaskStop` a browser agent because of a
  quiet period or a "looks frozen" inference. Stop **only** on an explicit user request or a
  real surfaced error. Browser steps legitimately pause between actions.

### Browser playbook (`vox-browser/SKILL.md`)
Note that browser steps legitimately pause (page loads, model think-time between clicks), and
emit periodic progress where the harness allows, so a backgrounded run reads as alive.

### Verification
Prose behavior — `tools/validate_skills.py skills` passes; covered in the same live-rigor
lodging spot check as A5 (which exercises the background browser path).

---

## Out of scope (deferred)

- **P2 backlog** from the findings doc: A3 (drop the redundant SendMessage probe), A4 (Wave-1
  logistics browser dispatch), A6 (duplicate-URL / comment-permalink render checks), A8
  (aggregator re-quote after a primary 403), A9 (vox-x geo filter), A11 (pre-fan-out premise
  check), A12 (auto-select single Chrome), A13 (re-run hint on unauth tier), A10 residue
  (carry hard constraints forward). Candidates for a v2 batch.
- **gosom volume via a deeper detail-page scrape** (`-depth 2` / primary-record reconcile)
  beyond the single category re-fetch — only if the one re-fetch proves insufficient in practice.
- The parked **menu/photo extraction** feature (separate brainstorm).

## Acceptance
- maps-cli quality gate green (`pytest`, `ruff`), with the new A7 tests.
- vox gate green (`validate_skills.py skills` prints `[ok]` for every skill).
- A live-rigor lodging query exercises A5 (brand-verify the top-3, tag the picks) and A14
  (narrated background browser, no self-stop).
