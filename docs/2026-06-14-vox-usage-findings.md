# Vox usage-run findings & action backlog

**Date:** 2026-06-14
**Status:** Validated. A first-pass audit (Sonnet analyzers + Opus synthesis) over-stated
severity and produced several artifact-driven false positives; a second **Opus re-validation
pass with an `isMeta`-aware transcript reader** corrected every finding against raw evidence.
This document reflects the **re-validated** backlog. The headline change: **there are no P0s.**

**Method.** A workflow analyzed every Claude Code session that invoked the `vox` skill —
**19 sessions (06-07 → 06-14), 18 real recommendation runs** + 1 meta. Then 12 Opus agents
re-checked each surviving finding against an `isMeta`-aware flattened transcript (every user
message tagged `[USER-REAL]` vs `[USER-META]`; `[BRIDGE-SESSION]` resume boundaries and
client socket errors surfaced), retracting anything that rested on a harness artifact. The
current dev session is excluded (already in the roadmap).

**Corpus mix:** sentiment (Mr&Mrs Smith, Obsession, NYC homelessness, BLS credibility, Claude
Fable drop), places (SoHo dinner, KBBQ, dessert, Flatiron lunch, Grafton, Aventura housing,
LGA hotels), logistics (bagel least-detour, Knicks-game viewing), general research (audio-sync
apps, MARTA shooting, savings accounts), video/bookmarks (Twitter bookmark recall). Every run
delivered; **zero fabrications** in vox's own output.

---

## What the re-validation taught us (method note)

Two classes of error in the first pass, both now corrected:

1. **`isMeta` contamination.** The first flattener dropped the `isMeta` flag, so
   harness-injected messages read as user input. This produced two false-positive P0s, both
   **retracted**:
   - *A1 (ConnectionRefused)* — the errors (`4caa76e8:516`, `afa9b3e8:570`, `6e4564dd:2217`)
     are the Claude Code client losing its API socket on **laptop sleep / Wi-Fi drop** — not vox.
   - *A2 ("No response requested")* — "Continue from where you left off." is an `isMeta:true`
     message at a `bridge-session` resume boundary (`0f8c012f:198`). vox's reply was **correct**.
2. **Over-claiming.** The synthesis inflated specifics that the raw transcripts contradict:
   "scoreboard omitted entirely (aca68001)" was **false** (it rendered a full scoreboard);
   "3 failed `vox-reddit`-type calls **every run**" was **false** (1 of 7 sessions); the HYSA
   "stale APY" was actually vox **catching and correcting** the staleness; one action cited a
   commit `e97e2e8b` that **does not exist**. These are corrected/dropped below.

The lesson is logged to memory: filter `isMeta`/`bridge-session` before counting a "user"
message as real, and pin every claim to a raw line.

---

## What works well (protect against regression)

Several first-pass "bugs" turned out to be vox doing the **right** thing — these are strengths:

- **Honest staleness correction.** On the savings query, vox detected a ~1-point conflict
  between aggregator APYs and a dated primary (Ken Tumin), re-fetched, and ranked on the
  corrected 3.0–3.4% (`aca68001:325/352`). (This is why A5's HYSA half was dropped.)
- **Follow-up re-weighting.** The $30/pp budget change was re-weighted over the existing pool,
  not restarted (`9458b053:449`), and the Baekjeong CLOSED flag was preserved across runs.
  (This is why A10's headline was retracted.)
- **Correct degradation when a tool is genuinely absent.** `SendMessage` is truly unavailable
  in this harness (`ToolSearch(select:SendMessage)` → "No matching deferred tools found" in
  every session); vox's "SendMessage isn't available, dispatching fresh with carried context"
  is **correct behavior** (`ba5af1b9:597`).
- **Parallel Wave-1 fan-out**, **mandatory conflict-trigger re-fetches** before render,
  **honest premise-correction**, the specific **`Sources that failed / blocked`** line,
  **closure/defunct detection**, the **anti-bot ladder** (403 → Firecrawl/`needs-browser`,
  never retry), and **`volume-UNAVAILABLE` instead of fabricating "0 reviews"** all held.

---

## Validated backlog

### P0 — none.

All four first-pass P0s fell: A1/A2 retracted (artifacts); A3 reframed to P2 (vox behaves
correctly); A4 narrowed to P2 (browser *was* dispatched for inventory); A5 split, with the
real half landing at P1.

### P1 — verified, worth building (3)

**A5. Verify live place/price availability on the brand engine before presenting it as
bookable.** In the LGA-hotels run, vox presented Google-Hotels aggregator prices (DoubleTree
LIC $189, Hyatt Place LIC $203) as recommended bookable picks with only a soft "rates can
move" hedge (`e4dbd299:949/951/957`). A genuine `[USER-REAL]` challenge ("Did you check…the
actual hotel websites?", `e4dbd299:967`) plus the user's pasted sold-out hilton.com URL forced
a walk-back: the brand-site check showed Hyatt Place LIC was **"Hotel Not Available"**
("Google said $203 available — wrong", `e4dbd299:1218`) and DoubleTree's true rate was
$259/$239, not $189 (`:1044`). **Fix:** in the place/price path, treat aggregator (Google
Hotels/Booking) prices as availability *signals only* and verify the specific finalist on the
brand booking engine (browser rung) **before** ranking it as bookable — not reactively.
*Scope note:* the original "HYSA APY" half is **dropped** — vox handled that correctly.
*Target:* `vox SKILL.md` (Wave-2 place-price verify) + `vox-maps`/`vox-browser`. *Effort:* M.

**A7. Treat gosom `reviewCount==0/null` as `volume-UNAVAILABLE` at the scraper level, and
reconcile/carry the volume.** gosom's list-card `reviewCount` extraction returns 0 (or a
different non-zero) for the **same** place across repeat fetches under varying Google DOM
variants — the load-bearing proof is the bagel run's same-shop divergence (Tompkins
**860 vs 0**, `e97e2e8b:325`; Zucker's 463 vs 0 vs 0, `:341`), echoed in the Flatiron/SoHo/
KBBQ runs. Since review **volume** is the headline rating×volume signal, a 0/null collapses or
omits a finalist's score, and Reddit/web finalists reach the scoreboard with no volume at all.
**Fix:** (1) treat `reviewCount==0/null` as `volume-UNAVAILABLE` at the scraper level (not a
real 0); (2) retry/cross-source list-card vs primary-record volume and reconcile; (3) carry the
single reconciled volume forward across session resumes so a finalist's number can't mutate.
*Scope note:* the cited **5,526-vs-462** KBBQ pair is **not** a gosom divergence — gosom
consistently returned 5,526; the 462 is a later orchestrator-side carryover, which is exactly
what fix (3) addresses. *Target:* `maps-cli` (gosom normalize) + `vox-maps SKILL.md`. *Effort:* M.

**A14. Don't silently background a browser sub-task that holds the user's Chrome — and never
self-stop it on an inferred stall.** In the LGA-hotels run vox silently dispatched a background
browser agent (`e4dbd299:533/538`), then **killed its own correctly-working agent** via
TaskStop on a self-inferred "frozen" signal (`:570`) — admitting *"it wasn't actually frozen …
My mistake was launching it in the background so you got no narration"* (`:576`). *(Causal
correction: this was vox stopping its own agent, not a user ESC.)* **Fix:** run a browser
sub-task that holds the user's Chrome in the **foreground with step-by-step narration** (vox
self-proposed this at `:583/591`); if backgrounded, narrate the launch and never treat a quiet
30–60s gap between clicks as a hang. *Target:* `vox SKILL.md` (browser tier) + `vox-browser
SKILL.md`. *Effort:* S.

### P2 — real but minor / narrowed (build opportunistically)

**A3. Drop the redundant `SendMessage` ToolSearch probe on follow-ups.** `SendMessage` is
genuinely unavailable here; vox already recovers correctly by dispatching fresh agents with
carried context — so just skip the probe. *(The "3 failed `vox-*` agent-type calls every run"
claim is **false** — it happened in 1 of 7 sessions; dispatch is otherwise already correct.)*
*Target:* `vox SKILL.md`. *Effort:* S.

**A4. For logistics/transit sub-questions, dispatch `vox-browser` for live Maps directions in
Wave 1** (per the skill's own `logistics → always vox-browser` rule), and route `vox-maps`
`escalate-to-browser` finalists to Chrome instead of leaving them as hand-estimates. In the
dessert run the real-Chrome tier was never invoked, transit times were hand-estimated, and a
flagged finalist (Keki) went unverified — drawing the genuine `[USER-REAL]` *"Are agents
properly utilizing Chrome?"* (`4caa76e8:433`). *(Generalized "browser under-dispatched for
inventory" claims **retracted** — it was dispatched in the Aventura and LGA runs.)* *Target:*
`vox SKILL.md` (step 2 routing). *Effort:* S–M.

**A6. Two real render-gate defects** (the other 5 first-pass sub-claims are unconfirmed/false):
(1) a render-time check that each scoreboard row's distinct listing maps to a **distinct URL**
(`0f8c012f:472` reused one Furnished Finder URL for two properties); (2) enforce **comment
permalinks** (not the thread root) in citations (`c512ffa8:260-264`). *Target:* `vox SKILL.md`
(citation gate) + `references/output-template.md`. *Effort:* S.

**A8. When a primary source is 403-blocked, an aggregator re-quote must not become the sole
basis of a load-bearing claim** without a confidence downgrade or browser escalation. Holds for
**1 of 4** first-pass cases (the Notability #1 note-app pick rested on checkthat.ai re-quoting
Gingerlabs after a 403, `6ec16c08:415`). *Target:* `vox-web SKILL.md`. *Effort:* S.

**A9. Add a geo constraint to the `vox-x`/bird query layer (or make X conditional) for
hyperlocal place queries.** bird has no geo filter, so NYC place runs pull heavy off-geo noise
(SoHo→Rome/London/San Diego) — ~7–19 searches/run for thin local yield while consuming a full
agent slot (`1f41c1af:253`). *(Magnitude corrected from "11–19" to ~7–19.)* *Target:*
`vox SKILL.md` (step 2) + `vox-x SKILL.md`. *Effort:* M.

**A11. Add a one-shot pre-fan-out sanity check** on load-bearing user premises (e.g. home/away
schedule) and vox's own date/leadership priors, plus a recency caveat on sources older than
~12 months. *(Reframe: "catch it earlier/cheaper," not "vox invented a falsehood" — in 3 of 4
cases vox self-corrected, just late; only the year-old Obsidian thread needed user pushback,
`6ec16c08:445`.)* *Target:* `vox SKILL.md` (steps 1/2) + `vox-web`/`vox-reddit`. *Effort:* M.

**A12. Auto-select Chrome when exactly one browser is connected** — skip the AskUserQuestion and
`select_browser` the lone deviceId (`6e4564dd:776/779`, `e4dbd299:364/367/370`). *(Drop the
first-pass "feasible per commit e97e2e8b" rationale — that commit doesn't exist.)* *Target:*
`vox SKILL.md` (browser tier) + `vox-browser SKILL.md`. *Effort:* S.

**A13. Append a recovery + re-run hint to the `Sources that failed / blocked` block** when a
tier (esp. X/bird) is unauthenticated/unavailable (the auth command + "then re-run for that
source's coverage"). In the MARTA run vox declared the X-unauth degradation three times but
offered no recovery path, and the user re-typed the identical query verbatim (`88fb1431:4` →
`:316`, both `[USER-REAL]`). *Target:* `vox SKILL.md` (step 0 / step 7). *Effort:* S.

**A10. (mostly retracted)** Only residue: carry a prior-turn **hard constraint** forward into a
new run — a "dinner only" constraint added then re-issued without it was never re-surfaced
(`9458b053:524/527`). The headline ("follow-ups restart and lose state") is **retracted** —
vox re-weighted correctly and preserved entity flags. *Target:* `vox SKILL.md` (step 1/8).
*Effort:* S.

---

## Structural coverage gaps (validated)

- **Places ranking depends on a fragile signal** — gosom `reviewCount` is unreliable across DOM
  variants (A7), exactly on the most common query type.
- **Aggregator price/availability** (Google Hotels/Booking) is not the same as bookable
  inventory; vox needs a brand-engine confirmation step before recommending (A5).
- **X has no geo filter** — structurally noisy for hyperlocal queries (A9).
- **Browser sub-tasks that hold the user's Chrome** need foreground narration; silent
  backgrounding invites a false-stall self-stop (A14).
- **No `SendMessage`** means agent continuation is impossible — follow-ups must carry a
  prior-session summary forward (vox already does; A3 just removes the wasted probe).

---

## Per-session outcome table (isMeta-corrected real-user-turn counts)

| Date | Type | Outcome | Real user turns | isMeta | Query |
|------|------|---------|-----------------|--------|-------|
| 06-07 | sentiment | ranked | 15 | 2 | Mr & Mrs Smith ending |
| 06-08 | sentiment | degraded | 5 | 1 | Obsession critic/fan analysis |
| 06-08 | video/bookmarks | ranked | 8 | 1 | Twitter bookmark recall (kittylitter) |
| 06-09 | sentiment | ranked | 8 | 1 | NYC homelessness sentiment |
| 06-09 | general | ranked | 15 | 1 | Audio-synced note apps (macOS) |
| 06-09 | general | ranked | 13 | 1 | BLS report credibility |
| 06-09 | places | ranked | 8 | 1 | Dinner SoHo near MoMA Store |
| 06-09 | general | ranked | 18 | 2 | MARTA shooting ATL |
| 06-10 | places | degraded | 16 | 1 | Dessert near Cho Dang Gol |
| 06-10 | places | ranked | 34 | 2 | Koreatown KBBQ $40-50pp |
| 06-10 | sentiment | ranked | 36 | 4 | Claude Mythos/Fable drop |
| 06-11 | places | degraded | 60 | 4 | Bars/restaurants near The Grafton |
| 06-11 | logistics | degraded | 23 | 2 | Where to watch the Knicks game |
| 06-11 | places | ranked | 34 | 2 | Lunch near Flatiron <$20 |
| 06-12 | logistics | ranked | 12 | 1 | Bagel least-detour (Brooklyn route) |
| 06-12 | places | ranked | 26 | 2 | Aventura housing (3-6mo lease) |
| 06-13 | places | ranked | 64 | 4 | Hotels near LGA (flight contingency) |
| 06-14 | general | ranked | 16 | 2 | Best savings account ($2k→$7k) |

*(The 06-12 session-export/upload run was meta — no vox run.)*

---

## Live-rigor validation (2026-06-15) — vox usage-fix v1

A real lodging query ("hotels near LGA, one night 2026-06-20→21, 1 adult, verify bookable")
exercised the three shipped fixes end-to-end (Chrome paired, real brand engines):

- **A5 — VALIDATED.** Top-3 finalists (DoubleTree/Hampton/Marriott LGA) were verified on their
  own brand engines (hilton.com `NYCLGDT`/`NYCLAHX`, marriott.com `LGAAP`); each pick carried
  `brand-verified ✓`; the **aggregator-vs-brand gap was +$48 / +$170 / +$200** — exactly the
  trap A5 prevents (Hampton aggregator ~$124 vs real $297). Read-only confirmed.
- **A14 — VALIDATED.** Background browser launch was narrated ("quiet gaps normal, won't stop
  it"); the single agent ran ~4 min serially and returned cleanly; no self-stop.
- **A7 — logic correct but gated** (see new finding below). `reviewCountStatus` + the category
  re-fetch worked (recovered Aloft→919, Comfort→482; left Holiday Inn Express + the closed
  Courtyard `⚠ volume-UNAVAILABLE`, never `×0`), but only via maps-cli's own modules — not
  through the `maps-cli places` CLI, which is blocked end-to-end (next).

### NEW finding (P1, deferred to a follow-up) — `maps-cli places` 5s-inactivity timeout

`maps_cli/gosom.py:60` hardcodes `-exit-on-inactivity 5s`. A cold chromium start loses that
race, so gosom self-exits before scraping, writes empty results, the one retry hits the same
race, and `run_gosom` raises `BlockedError` — **every `maps-cli places` call exit-3s on a cold
start** (reproduced independently: `maps-cli places "NYC LaGuardia Airport Marriott" --near …`
→ "gosom returned no results after a retry" in ~32s). The existing tests miss it because they
use a fake gosom binary, not real chromium. **Impact:** the entire places tier (and thus A7's
value) is inert through the real CLI until fixed. **Fix (one line, deferred per user):** make
`-exit-on-inactivity` configurable (e.g. `MAPS_CLI_GOSOM_INACTIVITY`) with a ~30s default, or
bump the literal `5s`→`30s`; add a test that asserts the flag value. Target: `maps-cli/maps_cli/gosom.py`.
