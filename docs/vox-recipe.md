# Vox Recipe: Synthesized from 187 Mined Findings

> **Provenance note.** This recipe is grounded in prior sessions that ran a 4-channel restaurant-recommendation pipeline (Reddit `reddit-cli`, X `bird`, Web `WebFetch`/`WebSearch`, Google Maps via Claude-in-Chrome). The findings are **dense and consistent** for those four sources. They contain **NO observed sessions for TikTok (`tiktok-cli`) or Instagram** — those subsections below are extrapolated from the cross-source patterns and the project's known constraints (lazy `TikTokApi` import, no browser binaries in the gate), and are explicitly flagged as unverified. Do not treat them as battle-tested.

---

## 1. Orchestration recipe

The flow that repeatedly worked, as concrete ordered steps. The domain was restaurants; the **shape** generalizes directly to "best-informed recommendations / sentiment on a topic."

### Step 0 — Verify tools exist before planning
The very first action was capability probing, not decomposition. The orchestrator ran `which bird reddit-cli`, `bird --help`, `reddit-cli --help`, `claude mcp list`, `ps aux | grep remote-debugging`, `curl …9222` to confirm each named tool was actually present. When Claude-in-Chrome was unavailable, it **named the two criteria that depended on it** and substituted lower-confidence web methods rather than silently degrading or fabricating output.
> *"Claude in Chrome — not available… I won't fake either of those — instead I'll substitute web-based methods… and I'll mark those two with lower confidence."*

**Rule for Vox:** never assume a named source CLI is installed. Probe, and if a source is missing, declare which sub-questions lose coverage.

### Step 1 — Decompose the query into sub-questions, then route each to its purpose-fit source
Each sub-question was mapped to the source best suited to answer it (see §4 for the full routing table). The key move: **one tool per subagent**, except shared stateful resources (the browser) which the orchestrator drives itself.

### Step 2 — Create explicit task items mirroring the user's stated criteria, then REORDER by leverage
The orchestrator front-loaded the user's stated ordering into `TaskCreate` items (one per criterion), but executed by **difficulty/leverage**: it tackled the user-flagged hardest criterion (transit detour) early because it reshaped the whole candidate set, while discovery agents ran async in the background.
> *"let me tackle the criterion you flagged as hardest — the detour"* while *"3 discovery agents finish"*; the detour checks *"just reshaped everything."*

**Rule for Vox:** preserve the user's priority order for *ranking*, but order *execution* by which check most prunes the candidate set. Run the expensive-but-decisive filter first.

### Step 3 — Launch discovery subagents async, one per source, with strict briefs
Discovery agents were launched in the background (`Agent` tool, `agentId` returned, completion notifications). Each brief:
- names the exact target(s) and the **source priority order**,
- specifies the exact fields to extract,
- includes a prior claim to verify,
- demands an honest caveats/unconfirmed section and **forbids fabrication**,
- instructs the agent to establish the CLI's real capabilities first (`bird --help`, `reddit-cli search --help`).

The orchestrator **never reads the subagent JSONL `output_file` directly** (would overflow context — each launch returns an explicit warning about this) and works non-overlapping tasks while they run.

### Step 4 — Drive shared stateful resources directly; keep stateless agents parallel
Only one agent can drive Claude-in-Chrome at a time (single paired browser, one shared tab group), so the orchestrator drove Maps itself and restricted all subagents to stateless `WebFetch`+`WebSearch` (every agent prompt literally said *"use ONLY WebFetch and WebSearch (NO browser/Chrome tools)"*). N stateless HTTP agents parallelize with zero tab contention.

### Step 5 — Process completions incrementally
As each menu-read agent returned, the orchestrator posted a running progress line (`"Menu reads: 1/9 in… Waiting on the other 8"`) with a one-sentence verdict per finalist, then compiled the full ranked table **only once all were in**. Keeps the user informed without premature ranking.

### Step 6 — Two-tier verification before ranking
Coarse cheap signals (Maps `$10–20/person` bands) triaged many candidates fast; expensive precise signals (real menu reads) were spent only on finalists. The orchestrator disclosed which numbers were band-estimates vs verified (see §4).

### Step 7 — Synthesize into the fixed template; gate on cross-source corroboration
Finalists had to appear in **2+ of the channels** to make the shortlist. The deliverable followed a reused skeleton (§3).

### Step 8 — Treat constraint changes as RE-WEIGHTING, not restart
When the user said *"time isn't an issue,"* the detour column dropped to near-zero weight and goodness/value rose — live, without re-running discovery. A new axis (*"eat in bed, no splatter"*) became a new screening filter that re-sorted the existing candidates into tiers.

### Step 9 — Self-diagnose blind spots on pushback
When challenged (*"Why no Manhattan picks?"*), the orchestrator diagnosed the root cause in its **own decomposition** (*"I over-applied minimal-detour = at-the-destination"*), re-ran the identical measurement on the user's own examples (treating user-provided receipts as ground-truth anchors), and produced a rebalanced ranking. It owned the miss explicitly rather than defending.

---

## 2. Per-source playbooks

### 2.1 Reddit — `reddit-cli`

**Tool surface (verified).** Homebrew binary at `/opt/homebrew/bin/reddit-cli`. Subcommands: `browse`, `search`, `post`, `user`, `comments`.
- `search [OPTIONS] <QUERY>`: `-r/--subreddit`, `-s/--sort [relevance|hot|top|new|comments]` (default `relevance`), `-l/--limit`.
- `comments <POST_ID|URL>`: `-s/--sort [best|top|new|controversial|old|qa]`, `-l/--limit`.
- `post <POST_ID|URL>`: `-l` limit, `-d` comment depth.

Always run `reddit-cli --help` then `reddit-cli search --help; reddit-cli comments --help; reddit-cli browse --help` (echo-separated) before real queries.

**Getting good signal.**
1. Run several **broad + scoped** parallel searches to collect post IDs, then drill into the highest-comment threads: `reddit-cli comments <id> -s top -l 40..60`. Prior runs pulled comments from ~8–10 thread IDs.
2. **Always scope to relevant subreddits with `-r` and use `-s relevance`.** Unscoped global `-s top` returns viral junk (TIFU, r/mildlyinfuriating, r/bayarea for "Sunset" — wrong coast). Scoped `-r FoodNYC -s relevance` surfaced the on-target thread.
3. Rank by **cross-thread recurrence**, not single-thread upvotes: named across many independent threads = Tier 1; named once = flag as "single-thread / one person's opinion." Track per-item: name, raved points, value quotes, consensus strength. **Flag genuine opinion splits** instead of forcing a winner; include an "anti-recommendation" section.
4. Inject real-world sanity checks (one worker corrected a route premise the brief assumed wrong).

**Output shape.** Group by relevance/tier or zone; per item: name + key detail, paraphrased/short-quoted line with upvotes, citation (`subreddit + comments/ID`), and a **STRONG/MODERATE-STRONG/MODERATE** strength label. Separate in-budget/in-scope picks from "beloved but out-of-scope" rather than dropping them. Close with a notes/caveats section flagging which generic searches returned noise.

**Pitfalls.**
- **Do not** use command-substitution to derive post IDs (`reddit-cli post .../$(reddit-cli search …)/`) — it silently resolves the wrong post. Run a plain search, read the printed URL, then call `comments` with the literal URL in a separate step.
- Empty-ID calls error `Invalid post ID`.
- Reddit-via-`WebSearch` is unreliable (`"No links found"` is common) — use the CLI, not web search, for Reddit.

### 2.2 X / Twitter — `bird`

**Tool surface (verified).** `bird` v0.8.0, pre-authenticated X/GraphQL client; auth sourced from Safari cookies. **It HAS a `search` subcommand** (some briefs wrongly assumed it didn't — verify the binary, don't trust the brief).
- Bootstrap: `bird --version; bird --help; bird search --help`, then `bird check` (prints `auth_token`/`ct0` status + browser source), `bird whoami`.
- Search: `bird search "<query>" -n <count> --json` (or `--plain`). Supports `from:` and `@handle` operators; flags `-n/--count`, `--all`, `--max-pages`, `--cursor`, `--json`, `--json-full`.

**Getting good signal.**
1. **Two-stage query progression:** broad area queries to surface candidate names → targeted per-name queries to confirm sentiment with representative tweets. ~10–14 searches total.
2. **Specific named-venue queries return the richest hits; generic terms return noise.** `"Szechuan Mountain House Flushing"` surfaced the NYT-100-Best list; `"cheap eats"` pulled spam.
3. Batch many searches in one Bash call via a for-loop over a query array, piping each through a small parser. **Write a helper script** (`/tmp/fmt.py` iterating `for t in json.load(sys.stdin)`) — inline `python3 -c` with a list-comprehension containing `print` raises `SyntaxError`.
4. Rank by count of **independent corroborating users**; capture verbatim tweet text + permalink per claim; **actively flag closure/negative signals** (a Mar-2025 tweet flagged a spot as permanently closed → "do not route here").

**Output shape.** Lead with a `BIRD CAPABILITIES` section (what worked, auth status, "this is real data, not fabricated"). Then per-item: name + (category/location) + **bolded sentiment label** (Strongly positive / Positive but pricey / Mixed) + paraphrased quote (<15 words) with `@handle` + permalink. Close with a best-corroborated shortlist and a caveats/"what didn't work" section.

**Pitfalls / anti-bot.**
- **No geo filter** — location queries pull heavy noise (`"Sunset Park takeout"` → horse-racing "takeout rates"; `"flushing"` → toilets/medical). Many real hits are years old.
- Short/OR queries match substrings in foreign-language tweets (`"sodi"` matched unrelated text) — discard.
- Many queries return zero results — **report no-result honestly, never invent**. Some neighborhoods returned "No tweets found" repeatedly.
- A single high-signal food-writer account often supplies most specific detail — worth leaning on.

### 2.3 Web / Google — `WebFetch` + `WebSearch` (+ Claude-in-Chrome for Maps)

**Tool surface (verified).** `WebFetch` and `WebSearch` are **deferred tools** — every worker's literal first action is `ToolSearch( select:WebSearch,WebFetch )`. Calling them cold fails with `InputValidationError`. `WebSearch` accepts `allowed_domains` to scope the index to one site (useful to pull prices out of a JS-rendered page the index has crawled but `WebFetch` can't render — though results are inconsistent).

**Getting good signal.**
1. **Parallelize aggressively.** Fire 2–4 independent `WebSearch`/`WebFetch` calls per turn (one per candidate, or official-site + aggregator simultaneously). Only sequence when a later fetch depends on a URL discovered earlier. Typical worker: `ToolSearch` → 2–3 parallel `WebSearch` → 2 parallel `WebFetch` (primary + corroborating) → verify → one more for sentiment → synthesize. Finished in ~5–8 calls when sources cooperated.
2. **`WebFetch` prompts are directive extraction specs, not "summarize."** Name the exact fields/items to pull and ask it to confirm the entity's address/identity. Generic prompts waste the fetch.
3. **`WebSearch` snippets and result-page TITLES are first-class data**, not just link discovery — they reliably surface prices, ratings, and review counts even when the underlying page `WebFetch` is 403'd.
4. **Source ladder (most→least fetchable):**
   - **Fetchable cleanly:** Slice (`slicelife.com`), official non-JS sites, MenuPages, `allmenus.com`, Chowbus (`pos.chowbus.com`), Postmates store pages, Yelp **`/menu/<slug>`** path (not `/biz/`), RestaurantGuru, Restaurantji, The Infatuation, Tripadvisor, Wanderlog, critic Substacks (Sietsema), Michelin description text.
   - **Often blocked / JS-stub** (see §5): Yelp `/biz/`, DoorDash, Seamless, Grubhub, Toast, Square/`baemenu`, official "Order Now" ordering apps, Michelin Guide pages.
5. **Aggregator slugs are unguessable** — RestaurantGuru/Restaurantji guessed slugs 404. `WebSearch '<name> <city> restaurantguru.com'` first to discover the real slug, then fetch.

**Claude-in-Chrome (Google Maps) — only when present, driven by orchestrator only.**
- Tools are **deferred/lazy** — pull each by exact MCP name via `ToolSearch(select:mcp__claude-in-chrome__…)`. Generic keyword searches return nothing.
- Pairing is a gated handshake: `list_connected_browsers` → `AskUserQuestion` (which browser) → `select_browser(deviceId)` → `tabs_context_mcp(createIfEmpty:true)`.
- **Navigate via direct URL, not UI typing.** Two patterns do all the work: `/maps/search/<url-encoded query>/@lat,lng,zoom` (returns `Name 4.5(7,129) · $20-30 · cuisine · address`) and `/maps/dir/?api=1&origin=…&destination=…&travelmode=transit`.
- **Prefer `get_page_text` over screenshots** for result lists — parses rating/count/price/cuisine cleanly, no OCR.
- Bundle actions in `browser_batch`, but **text grabs inside a batch fire before Maps renders** → split into `navigate → wait → get_page_text`.
- Clicking into place panels is flaky (`ref_49` was the global hamburger, not the Menu tab). Recovery ladder: `read_page(filter:'interactive')` → grab canonical `/maps/place/…` URL → navigate directly. When a Maps menu photo is a low-res thumbnail, **abandon OCR and hand off to a `WebFetch` subagent** reading the live menu.

### 2.4 Google Maps / places

Covered above for mechanics. Two semantic lessons worth isolating:
- **Maps `$ per person` bands are coarse, per-person estimates — NOT menu prices.** Use them only for initial triage; replace with verified reads for finalists and **disclose which is which**. A `$1–10` band hid an actual `$4.36/slice`; a "5.0 best slice" was a personal-pizza shop with no slices that could bust the budget.
- **Maps cannot compute multi-stop transit routes** (waypoint → *"could not calculate transit directions,"* offers only driving). Derive a "detour with a stop" as **two sequential transit legs (origin→place, place→destination) minus a measured baseline**. Out-and-back walking overstates it.

### 2.5 TikTok — `tiktok-cli` *(NO prior-session evidence — extrapolated)*

**Honest gap:** none of the 187 findings touch TikTok. Treat this as a design sketch, not a recipe. From the project memory: lazy `TikTokApi` import, no browser binaries in the gate environment.

Recommended starting design, mirroring the verified patterns:
- **Bootstrap identically:** `tiktok-cli --help` and per-subcommand `--help` before real queries; verify auth/capability and **declare honestly if search isn't supported** rather than fabricating.
- **Expect the bird-style failure modes:** no/weak geo filter, ambiguous-keyword noise, and zero-result queries — report empties honestly.
- Video is **expensive, low-density signal**: prefer it as a *corroboration/discovery* channel (surface buzzy names, capture creator sentiment + caption), not a precision-data channel. Defer to **later phase** per the user's plan.
- Output shape: mirror the X worker — capabilities header, per-item sentiment label + paraphrased caption/transcript quote + permalink, corroboration note, explicit caveats.

### 2.6 Instagram *(NO prior-session evidence — extrapolated)*

**Honest gap:** no findings. No Instagram CLI was probed in any session. Same caution as TikTok. Likely the hardest source for anti-bot and the lowest text-density; recommend deferring with TikTok to the places/video phase. If built, mirror the bird/TikTok worker contract (capabilities-first, sentiment + permalink, no fabrication).

---

## 3. Output format that worked

A **fixed, reused template** recurred verbatim across all three tasks (errand, dinner, Flushing):

1. **`## How I built this` / `Sources used`** — methodology preamble naming the discovery channels and how each metric was derived.
2. **`# Top 10` table** — single markdown table whose columns map **one-to-one** to the user's stated constraints, ordered by the user's declared priority. Example columns: `# | Place | Get this (for 2) | ~$ for 2 | Rating / sentiment | Portion | Detour`.
3. **`How to read it against your criteria`** — prose grouping picks by which constraint each one wins.
4. **Flags / Excluded / Splurge appendix** — constraint violations itemized with the **exact failing value** (over-budget band, over-cap detour minutes, permanently closed, cash-only). Never silently dropped, so the user can override.
5. **One honest single-line recommendation** ("My call: …").
6. **Closing offer of 2–3 concrete next actions** ("Want me to…").

Supporting elements:
- **Running scoreboard on demand:** per-source tally (web ~13 / Twitter ~10 / Reddit ~20 / Maps ~50) → deduped distinct total, with a funnel: surfaced → seriously evaluated → fit-the-filter → hard-excluded (with reasons). Grew across turns (~93 → ~123) — makes search breadth auditable.
- **Reframe the decision as a strategy with named buckets**, not just a list ("grab at origin" vs "grab at destination"; splatter Tier A/B/C).

**Per-source worker digest** (what each subagent returns to the orchestrator) — a tight, fixed structure:
- One-line entity classification ("what it is").
- A markdown table `Item | Price/Detail | Source-or-confidence`, every price carrying its **inline source URL**.
- Computed answer (e.g. per-person before tax/tip) **plus a leaner/minimal variant** as a range.
- Portion/yield verdict; goodness signals (rating + paraphrased <15-word quotes).
- An **explicit "Estimates labeled" block** and a **"Sources that failed (not used)"** list with the reason (403 vs JS shell vs not-listed) so the orchestrator trusts provenance and avoids re-trying dead sources.
- A `Bottom line for the orchestrator` TL;DR.

**Confidence discipline.** Conveyed **per-figure, not globally**: verified reads tagged `verified`; inferred values asterisked with a footnote; approximate answers given as bands (`~$26 light / ~$46 full`). Single-source numbers flagged as such; sample size honored (`4.9/207` on a young stall → "high confidence on quality, lower on consistency").

---

## 4. Ranking & cross-source verification

**Routing each sub-question to a purpose-fit source** (the core of the design):

| Sub-question | Primary source(s) |
|---|---|
| Objective goodness | Maps rating × **review-volume** + Yelp |
| Sentiment / anecdotal | `bird` (X) + `reddit-cli` + web critics (Infatuation, Eater, Michelin, NYT) |
| Precise facts (price) | real reads via `WebFetch` subagents — **NOT** Maps' coarse band |
| Route / logistics | Maps transit/walking in Chrome |

**Scoring rules:**
- **Goodness = rating × review-volume**, not raw stars. A 4.4 with 1,207 reviews beat thin 4.9s ("best vol × rating"); a Michelin-hyped spot was demoted for "only 4.2 on Google."
- **Cross-source corroboration is the promotion gate:** a candidate must appear in **2+ channels** to make finalists, and each pick is **labeled with which sources corroborated it** ("Twitter + Maps"). Single-source picks noted as such.
- **Apply the user's criteria order as an explicit gated filter** with a visible scoreboard + exclusion ledger. Hard-exclude over-budget / permanently-closed / structural-mismatch.
- **De-duplicate strictly by address.** Same-named locations differ in rating *and* price (two Andiamos, two King's Kitchens, Nan Xiang flagship vs Express which runs ~$2–4 cheaper). Wrong branch = wrong data.

**Two-tier verification:**
- **Coarse** (Maps bands) for triage → **precise** (menu reads, 2 corroborating sources) for finalists. The orchestrator **volunteered corrections** when caught conflating the two.
- Resolve conflicts by **recency and listing-type**: official site authoritative over stale aggregators; delivery-platform prices carry ~15–30% markup and are labeled a *ceiling*, not the dine-in figure; prefer **two agreeing current sources over one old one**. When official + delivery agree, **stop early** (strongest signal).
- **Confirm the entity before extracting** — wrong concept (a Neapolitan personal-pizza shop billed as a slice shop) means requested items genuinely don't exist → **report absence, refuse to fabricate**, return what *is* sold.
- **Sentiment drift** (not just current score): hunt dated reviews; use signal asymmetry (high average + high 1-star share = polarized, not declining). Reconcile incomparable scales (4.3 on Google-type vs 8.1/10 on critic) rather than averaging them.
- **Treat user-provided data as ground-truth anchors** and re-measure with the identical pipeline.

---

## 5. Pitfalls & anti-bot lessons (concrete)

**Anti-bot / fetch failure map (verified, repeated across workers):**
- **Hard 403 to `WebFetch` — do NOT retry, pivot immediately:** Yelp `/biz/` (and `m.yelp.com`), DoorDash, Seamless, Toast (`order.toasttab.com`), Michelin Guide, many official restaurant sites, `menu-world.com`/`restaurants-world.net` mirrors, sometimes Tripadvisor listing pages, PDF menu hosts. The 403 message itself suggests an authenticated tool.
- **`429 Too Many Requests` is terminal for the session** on aggregators like `corner.inc` — retried 3×, all 429'd. Move on.
- **JS-rendered stub signature:** Grubhub / Seamless / Square / `baemenu` / "Order Now" apps return only `"Prepare your taste buds..."`, `"Loading..."`, or the bare restaurant name. Recognize and abandon — don't re-prompt.
- **Workarounds that work:** pull ratings/review-counts straight from **`WebSearch` result-page titles** ("Updated June 2026 - 5349 Reviews") which Yelp keeps current despite the 403; use Yelp **`/menu/`** path (sometimes renders) instead of `/biz/`; fall back to Slice / RestaurantGuru / Restaurantji / Infatuation / Tripadvisor; for slice prices (online menus list only whole pies) pivot to **price-tracking journalism** rather than fabricating.

**Data-quality traps:**
- **Stale prices** from aggregators (allmenus showed `$4.50` vs current consensus `$10`). Cross-check 2+ recent sources; label old figures historical. Use internal inconsistency as the tell (a stale slice price implies a stale pie price).
- **Wrong TLD silently fails** (`thaivillany.com` ECONNREFUSED vs real `thaivillanyc.com`). ECONNREFUSED (bad domain) ≠ 403 (anti-bot) — different fixes.
- **Same-name / sibling / wrong-city contamination** is pervasive: a Koon Thai *Orlando* page for an NYC target; `woodamnyc.com` vs `woodamnj.com`; Bayside branch vs Flushing target; duplicate Yelp listings for one address. **Pin the address/domain up front; label distractors.**
- **Thin samples masquerading as authority** (Tripadvisor 5.0 from *n=1*, rank #5,862/13,566 — "ignore as a sample"). Always report N with the average.
- **Tripadvisor recency dried up** (newest fetchable reviews 2019–2020 even when the page loads) — verify a review's *date* before counting it "recent"; editorial reviews are often paywalled/stale.
- **Isolated negatives:** surface a lone food-safety review as a watch-item tagged "isolated, single mention" — neither bury nor headline it.
- **Correct false premises in the task** (asserted "signature mozzarella sticks" that don't exist) instead of fabricating to satisfy them.
- **Reddit-via-WebSearch** returns "No links found" often — use `reddit-cli`. **Reddit command-substitution** for post IDs silently grabs the wrong thread — separate the steps.
- **bird inline `python3 -c`** list-comprehension-with-`print` → `SyntaxError`; use a helper script.

---

## 6. Design implications for Vox

### Orchestrator skill
- **Capability-probe first, always.** Run `--help`/`which`/auth checks on every named source before planning; if a source is absent, declare which sub-questions lose coverage and substitute with a confidence penalty. Never fabricate a missing source's output.
- **Route by sub-question, not by "search everywhere."** Bake in the routing table: objective/quantitative → places + aggregators; sentiment/anecdotal → Reddit + X + web critics (+ TikTok/IG later); precise facts → directed `WebFetch`; logistics → Maps.
- **One subagent per source; keep stateful resources (browser) under direct orchestrator control.** Stateless HTTP agents parallelize freely; never delegate a single shared browser.
- **Never read subagent transcript files** — rely on their returned digest; warn agents this would overflow context.
- **Cross-source corroboration as the promotion gate (2+ sources)**, with each pick labeled by corroborating sources.
- **Two-tier verification:** cheap signal to triage, expensive verified reads only on finalists; disclose which is which.
- **Preserve user priority for ranking; order execution by leverage** (run the most-pruning check first).
- **Constraint changes = live re-weighting, not restart.** Maintain a re-sortable candidate set.
- **Process completions incrementally** with a running progress line; compile the final table only when all in.
- **Maintain an auditable scoreboard** (per-source tally → dedup total → funnel with exclusion reasons).
- **Self-diagnose on pushback** — own decomposition bugs, re-run the identical pipeline on user-supplied anchors.
- **Fixed output template** (§3) with per-figure confidence and an itemized flags/excluded section.

### Per-source subagent skills (shared contract)
Every subagent skill should enforce: **bootstrap (load deferred tools / verify CLI capabilities via `--help`) → establish auth → strict directive extraction → 2-source corroboration where possible → return the fixed digest with inline source URLs, an "estimates labeled" block, a "sources that failed" block, and a "bottom line" TL;DR → never fabricate; report absence/empties/no-result honestly.**

Source-specific must-haves:
- **Web:** first action `ToolSearch(select:WebSearch,WebFetch)`; parallelize 2–4 calls/turn; mine `WebSearch` titles/snippets as primary data; encode the source ladder and the 403/JS-stub blocklist so agents pivot instead of retrying; resolve conflicts by recency/listing-type.
- **Reddit:** always `-r <sub> -s relevance`; drill top-comment threads by literal URL; rank by cross-thread recurrence; flag splits; never command-substitute IDs.
- **X:** `bird check` first; two-stage broad→named queries; helper-script JSON parsing; rank by independent-user count; flag closures; report zero-results honestly.
- **Maps/Chrome:** lazy-load tools by exact MCP name; URL-navigate (search + dir patterns); `get_page_text` over screenshots; split batches around render waits; derive multi-stop transit as two legs minus baseline; hand menu photos to a `WebFetch` agent.

### What to build first
Build **text/sentiment-first**, exactly as the user wants, and exactly where the evidence is dense:
1. **Orchestrator skill** (routing, corroboration gate, scoreboard, fixed template, live re-weighting).
2. **Reddit subagent** (`reddit-cli`) and **X subagent** (`bird`) — both have fully verified tool surfaces and proven recipes.
3. **Web subagent** (`WebFetch`/`WebSearch`) — the workhorse; ships the source ladder, anti-bot blocklist, and directive-extraction prompts.
4. **Maps/places** as a Phase-2 add (depends on Claude-in-Chrome being paired; orchestrator-driven; gracefully degrades to web when absent).
5. **TikTok and Instagram LAST**, flagged as **unproven** — no prior-session evidence exists. Prototype them against the shared subagent contract, validate the actual CLI surface (`tiktok-cli --help`) before trusting any of the extrapolated design above, and keep them as discovery/corroboration channels, not precision-data sources.