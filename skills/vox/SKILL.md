---
name: vox
description: Search across Reddit, X, and the web for a ranked, cited, honestly-hedged recommendation or sentiment read on anything — "best running shoes", "how good is the new Claude model", "best ramen near Union Square". Use when the user asks what's best, what people think, or for a cross-source recommendation. Also use to rank the places in a TikTok/YouTube collection, playlist, or list of video URLs.
---

# vox — cross-source recommendation & sentiment orchestrator

You orchestrate Reddit + X + web (+ maps, browser, video) subagents into one ranked, cited answer.
Read-only. NEVER fabricate; degrade honestly. All work runs on the user's subscription.

## References
- Digest each subagent returns: [digest-contract](references/digest-contract.md)
- Final deliverable shape: [output-template](references/output-template.md)
- Query-rubric priors: [rubric-templates](references/rubric-templates.md)

## Loop
0. **Capability-probe** sources you'll use (`reddit-cli --help`, `bird check`,
   `ToolSearch(select:WebSearch,WebFetch)`; for the places tier `maps-cli doctor`; for the browser
   tier `ToolSearch(select:mcp__claude-in-chrome__…)` + `list_connected_browsers`; `vox-browser`
   picks the Chrome). If an HTTP source is missing, DECLARE which sub-questions lose
   coverage and proceed with a confidence penalty — never fake a missing source.
   The places/browser tier has a stricter rule: see the **Places & browser tier** section below.
1. **Parse** the query into an ordered criteria set (hard / soft / unknown). Locality and any
   user-named place/entity are HARD: if one is ambiguous or resolves to zero or several real-world
   matches (Union Square NYC vs SF), resolve it with one quick lookup; if still ambiguous, ask in
   step 1.5 even under "just run it".
   1.5 **Propose the rubric & confirm** (dimensions + source plan + "good" bar) per
   `references/rubric-templates.md`, UNLESS the query already states criteria or the user said
   "just run it" (then echo + proceed). **Record the output skeleton** (A = rankable
   finalists; B = no rankable finalist) as part of the confirmed rubric, by the rule rankable→A /
   else→B; carry it to render (step 7).
2. **Route** each sub-question to its purpose-fit source: objective goodness → web critics +
   review-volume; sentiment → X + Reddit + web; precise facts → directed WebFetch; **place data
   (rating × review-volume / hours / address) → the places tier (`vox-maps`, primary, parallel);
   logistics / transit detours / "detour with a stop" → the browser tier (`vox-browser`, Maps
   directions); general-search gaps + bot-blocked-but-important reads → the browser tier (Google)**.
   Mark which sub-questions NEED the places tier or browser tier (drives the Places-tier gate
   below). **Product / "is this a good price right now?" / price-history / shopping sub-questions → the
   product tier (`vox-amazon`, Wave 1, stateless, parallel)**; mark which finalists NEED the full daily
   curve (drives the Product-tier gate + Keepa escalation below). **TikTok/YouTube video URLs, playlists, or collections → the video tier (`vox-video`)**,
   which ingests each video and surfaces candidate places for the other sources to corroborate
   (drives the Video-tier gate below).
3. **Wave 1 — discovery.** Dispatch ONE subagent per source IN PARALLEL via the Agent tool. NOTE:
   every `vox-*` source (reddit, x, web, maps, browser, video, amazon) is a SKILL, not a registered agent
   type — dispatch each as `subagent_type: general-purpose` (or `Explore`) and tell it to invoke its
   `vox-<source>` skill as its FIRST action; never pass `subagent_type: vox-reddit/…` (it errors
   "Agent type not found"). Each brief (Wave-2 verifiers too) is self-contained: target, fields to
   extract, the digest contract, "ONLY your source's tools", "never fabricate", "use a generic
   User-Agent; never put the user's email in any header/UA", only candidate names the user gave or a
   source surfaced (never seed guesses), and an instruction to LOAD ITS PLAYBOOK FIRST (invoke its
   `vox-<source>` skill if available, else Read `~/.claude/skills/vox-<source>/SKILL.md`). A `vox-*`
   skill disabled via `skillOverrides` in `~/.claude/settings.json` is UNavailable; never reach it
   through this Read fallback. Work non-overlapping tasks while they run; do NOT read their
   transcript files — rely on the returned digest.
   When the INPUT is TikTok/YouTube video URLs, a playlist, or a collection, dispatch exactly ONE
   `vox-video` agent as the Wave-1 discovery driver (see **Video tier**); its surfaced entities are
   the candidate set the other sources corroborate (steps 4–5). `vox-maps` and `vox-browser` join this
   wave only under the timing in **Places & browser tier** below; `vox-amazon` joins it when a product
   sub-question is NEEDED and `amazon-cli doctor` is ok (see **Product & price-history tier**).
4. **Corroborate.** Build a candidate × source matrix; promote only candidates in 2+ channels;
   resolve same-name/duplicate collisions early; label each pick with its corroborating sources.
   If none reaches 2 channels, keep Skeleton A with the best single-channel candidates, each tagged
   `SINGLE-SOURCE`, and say in the lead-in that none cleared the bar. Before Wave 2, apply the hard
   constraint that eliminates the most candidates (closed / over budget / out of area).
5. **Wave 2 — verify (finalist OR contested claim).**
   - **Per-finalist (Skeleton A):** for each finalist, dispatch narrow stateless verifiers in
     parallel (for place finalists, `vox-maps` per finalist) to pin facts + recent sentiment (label
     each finalist `triaged` = snippet/listing-level only, or `verified` = page or record actually
     read).
   - **Conflict trigger (BOTH skeletons, MANDATORY):** if any digest's "Conflicts / disagreements"
     slot is non-empty, or a high-stakes claim (event date, toll, who/what/where) is contested or
     self-flagged a likely extraction error, you MUST resolve it before render — EVEN IF the headline
     facts already corroborate 2+ channels. The 2+-channel rule PROMOTES a candidate; it does NOT clear
     a conflicting figure. Resolve cheaply: ONE narrow re-fetch of just that fact (your own
     WebFetch/WebSearch; escalate to a directed `vox-web` verifier only if the re-fetch is itself
     blocked — never retry a 403/429).
   - **No-finalist branch (Skeleton B):** there is no per-finalist wave — instead run a lightweight
     corroboration pass: every load-bearing claim/number is in 2+ channels OR carries a single-source
     hedge, and each contested fact gets the one narrow re-fetch above. State in your reasoning that
     the per-finalist wave was intentionally skipped and why.
   - **Unresolved → disclose, don't pick:** if the re-fetch can't resolve it, render BOTH values with
     `⚠️ (sources disagree: X vs Y — unverified)`. Never silently choose one; the phrase "corroborated
     on every key fact" is FORBIDDEN while any conflict is open.
6. **Rank** by the user's priority order.
7. **Render** `references/output-template.md` with per-figure confidence (scoreboard on demand, per
   the template).
   For video-tier runs, add a **video-provenance** column (video URL + timestamp/frame, creator + COI,
   engagement) and list ingest failures (empty transcripts, unresolved entities, rate-limited comments)
   in the "Sources that failed / blocked" line.
   ALWAYS emit the canonical **Sources that failed / blocked** line (write `none — all fetches
   returned cleanly` when nothing failed) so coverage is explicit and machine-checkable.
   **Citation-completeness gate (before emitting):** carry every permalink forward from the subagent
   digests — every quoted string AND every standalone number/proportion/score in the final answer
   MUST sit next to an inline markdown link. A bare platform name (`(Reddit)`, plain `r/television`)
   or a floating score is NOT a citation. Self-check: scan the draft for quotation marks and numeric/
   `%` figures and confirm each is adjacent to a link; if a quote can't be linked, drop it; keep the
   claim only if another linked source supports it, else list it under Flags / excluded as unlinked.
   **Honesty gate (before emitting — provenance, not just adjacency; run as self-checks, no new
   agents):**
   1. **No silent confidence upgrade** — a fact any contributing digest marked `⚠️` / `SINGLE-SOURCE`
      / conflicting MUST keep at least that caution; you may LOWER confidence with justification but
      NEVER raise it above what the digest reported.
   2. **Per-claim sources** — tag each promoted fact with its real corroborating sources / channel
      count (`web-only`, `web+Reddit`); a blanket "all 2+ corroborated" is forbidden when any claim is
      1-channel.
   3. **Quote provenance** — a quote attributed to a NAMED person/outlet must link the page where it
      was actually READ. If recovered via an aggregator that re-quotes, strip the quotation marks and
      tag `[paraphrase via <aggregator>]`, or drop it — never render an aggregator re-quote as a
      verbatim attribution to the original.
   4. **Corroboration count links all N** — any count/strength claim ("N outlets", "genuine
      consensus") must inline-link EVERY counted source, or downgrade to a non-numeric hedge
      ("multiple critics"); a snippet-only / 403'd source may NOT be tallied into N.
8. **Follow-ups = live RE-WEIGHTING**, not restart: re-sort the existing candidate set.
9. **On pushback**, inspect your OWN decomposition for the blind spot, re-measure on any
   user-supplied anchors, and own the miss.

## Places & browser tier (places-first via gosom; browser = logistics + fallback; halt-by-default)
Place DATA (rating × review-volume / hours / address) is served by the **places tier**, available if
**`vox-maps` (gosom — `maps-cli doctor` exits 0) OR Chrome** is available. The browser is still a
SINGLE shared resource — never two `vox-browser` agents concurrently — and it owns
**logistics/transit** and serves as the **place-data fallback**.
Timing: `vox-maps` is the per-finalist verifier in step 5 (Wave 2), stateless and parallel; dispatch
it in Wave 1 only when the user's query itself names the places. `vox-browser` joins Wave 1 only for
logistics needs. Later escalations (a-data, b) go to that same agent via SendMessage if one exists;
otherwise dispatch one browser agent after Wave 1/2 with the batched queue (if an earlier browser
digest in this run reported `paired: <deviceId>`, pass that deviceId in the brief).
There are THREE triggers for browser work:
- **(a-data) Place data `vox-maps` could not serve** — every finalist of a `vox-maps` digest with
  Status `no-capability` or `blocked`, plus each finalist on a `needs-browser` line of a `partial`/`ok`
  one (exit 3, or a deciding figure volume-UNAVAILABLE). Escalate those sub-questions to `vox-browser`.
- **(a-logistics) Logistics / transit detours** — known at routing (step 2); gosom has no directions,
  so these always go to `vox-browser`. Dispatch the one browser agent in Wave 1 when logistics is
  needed.
- **(b) Bot-blocked-but-important reads** — discovered DURING Wave 1 by `vox-web`, which tags such
  URLs `needs-browser`.

- **Carry resolved review-volume forward.** Once a finalist's review volume is resolved in a
  run, reuse that reconciled number across session resumes / follow-ups — never let a finalist's
  volume silently change between turns (gosom can return a different list-card count on a later
  fetch; the first resolved value wins unless a verification step deliberately re-checks it).
- **Narrate the background browser; never self-stop on an inferred stall.** When you dispatch
  the single browser agent in the background, narrate at launch: what it's doing, which
  finalists it will visit, and that **Chrome will move on its own** and **quiet 30–60s gaps
  between clicks are normal, not a hang.** Do NOT `TaskStop` a browser agent because of a quiet
  period or a "looks frozen" inference — stop ONLY on an explicit user request or a real
  surfaced error. Browser steps legitimately pause between actions (page loads, model
  think-time).
- **Bookable picks carry a verification tag:** `brand-verified ✓` (rate + availability
  confirmed on the brand engine) or `aggregator-only ⚠` (price is a signal, not confirmed
  bookable). A sold-out finalist confirmed on the brand site is dropped or shown struck-through,
  never ranked #1.

### Bookable-inventory verification (lodging / housing)
When the query is **bookable-inventory** — lodging/housing intent (hotel, motel, inn, room,
stay, lodge, Airbnb / short-term rental, apartment, rental, lease, sublet) — AND the answer
will present a specific price/availability as actionable, then in **Wave 2** dispatch the single
`vox-browser` agent to verify the **top 3 finalists'** current availability + nightly price on
the **brand booking engine** (the property's own site, or the platform that actually takes the
booking) BEFORE ranking them as bookable. The three checks run serially through the one browser
agent. Aggregator prices (Google Hotels / Booking / Kayak snippets) are **availability signals
only** — they may rank candidates but may NOT be presented as "book this at $X" until brand-
verified. **No Chrome →** present aggregator prices with a `⚠ unverified — aggregator price,
confirm on the brand site` tag, never as a booking instruction (honest degrade, not a halt).

Availability gate (keyed off the routing-time PLACE / LOGISTICS need):
- **Place data needed + `vox-maps` available (`maps-cli doctor` ok)** → dispatch `vox-maps` per the
  timing above. Escalate ONLY the (a-data) finalists to `vox-browser` (when Chrome is up).
- **Place data needed + `vox-maps` UNavailable (exit 4) + Chrome available** → `vox-browser` serves the
  place data (its Maps playbook), as the fallback.
- **Logistics needed** → always `vox-browser` (one agent, Wave 1), independent of gosom.
- **Not needed** → ignore both tiers; run the HTTP tier as normal.
- **Logistics needed + Chrome UNavailable, or place data needed + BOTH gosom and Chrome UNavailable,
  default** → **HALT-AND-REPORT.** Do NOT silently produce a web-only answer. State which
  sub-questions depend on the places/browser tier, which of gosom / Chrome is unavailable, and the
  two ways forward: (a) pair Chrome / install gosom
  and re-ask, or (b) re-run with `--web-fallback`.
- **… + `--web-fallback`** (literal flag OR natural language like "proceed web-only if neither's up")
  → fall those sub-questions back to `vox-web`; mark every figure that lost places/browser
  corroboration with a LOWER-confidence mark + a one-line "no places/browser coverage" note.
A late `needs-browser` escalation (trigger b) that can't be served because Chrome is unavailable is
NOT a hard halt — `vox-web` already disclosed the gap. If a `needs-browser` page matters and Chrome is
unavailable or `vox-browser` could not read it, dispatch one directed `vox-web` verifier naming those
pages for its Firecrawl rung; otherwise note the gap and move on. A `vox-maps` or
`vox-browser` agent that returns `no-capability` or no usable digest (orphaned/dead) counts as
UNavailable for its sub-questions.

## Product & price-history tier (Amazon via amazon-cli; Keepa curve via the one browser)
Product / "is this a good price right now?" / "price history" / shopping sub-questions are served by
the **product tier** (`vox-amazon` → `amazon-cli`: curl_cffi search + CamelCamelCamel summary). It is
STATELESS and owns no shared resource, so it runs in **Wave 1 in parallel** with reddit/x/web. At routing (step 2), **mark which finalists NEED the full daily curve** — that drives the
Keepa escalation below. The full daily price-history (Keepa) needs the real Chrome and is served by the
SAME single `vox-browser` agent that owns logistics/place-fallback — never a second browser agent.

Availability gate (keyed off the routing-time PRODUCT / full-history need):
- **`amazon-cli doctor` ok** → dispatch `vox-amazon` in Wave 1 (stateless, parallel). It runs
  `amazon-cli search` (category) or resolves the ASIN directly (named product / ASIN / URL), then
  `amazon-cli price <ASIN>` per finalist for the current + CCC current/low/high/avg summary.
- **Full-history needed + Chrome up** → `vox-amazon` emits `needs-browser: keepa-history(asin=<ASIN>,
  domainId=1)` tags; escalate them to the single `vox-browser` agent (it captures Keepa and runs
  `amazon-cli keepa-decode` → `{current, series, stats}`), mirroring the vox-maps→vox-browser escalation.
- **Full-history needed + no Chrome** → degrade to the CCC summary (low/high/avg) with a confidence
  penalty + a one-line "no daily-curve coverage" note. Honest degrade, never a fabricated series.
- **`amazon-cli` unavailable (exit 4)** → declare lost Amazon coverage; proceed with the HTTP three.
- **Single-browser coordination:** if a run needs BOTH logistics AND Keepa history, the one
  `vox-browser` agent serves them SERIALLY (never a second browser agent).
- **No CAPTCHA solving** (restate the hard rule): an Amazon bot-check / Keepa Turnstile *interactive*
  challenge → `blocked` → degrade to CCC. Never solve, never bypass.
- **Honesty carry-through:** `priceStatus`/`reviewCountStatus == unavailable` render as `⚠`, never `0`;
  a `blocked` search is a partial candidate set, explicitly disclosed; cite every figure to the Amazon
  `/dp/<ASIN>` or CCC product URL.

`vox-amazon` is a SKILL, not a registered agent type — dispatch it in Wave 1 as
`subagent_type: general-purpose` (like `vox-maps`), told to invoke the `vox-amazon` skill as its FIRST
action; pin `model: opus`. Never pass `subagent_type: vox-amazon` (it errors "Agent type not found").

## Video tier (TikTok/YouTube video analyzer; halt-by-default on missing prereqs)
Triggered when the input is TikTok/YouTube video URLs, playlists, or collections (not a plain topic
query). `vox-video` is the candidate-discovery driver: it ingests each video (download → transcript
→ frames/vision → comments), extracts place claims under the five honesty rules, and returns the
digest; the stateless sources + browser then corroborate its candidates.
- **Capability**: `vox-video` owns its own probe. If it returns Status `no-capability` →
  **HALT-AND-REPORT** the missing tool + install it names; no partial answer, no `--web-fallback`
  (the videos ARE the source). A collection/playlist it cannot enumerate also returns
  `no-capability` asking for explicit video URLs: relay that ask, never report "0 videos".
- **Single video agent**: exactly one `vox-video` per run; it uses no Chrome, so it never contends
  with `vox-browser`.
- **Follow-ups**: re-weight the existing candidate set (step 8); never re-dispatch `vox-video` just
  to re-weight.
- **No phantom quotes**: a video whose transcript came back empty contributes on-screen/caption claims
  only — never a spoken quote.
- **No URLs**: if the user wants video signal but gave no URLs/collection, say the tier needs URLs
  and list it under Sources that failed.

## Hard rules
Cite every claim with a URL. 2+ sources to promote (else a `SINGLE-SOURCE` tag). Never retry a
403/429 (the web subagent pivots). When data is missing, say so and show the blocked/failed
sources. One honest pick, not a forced winner.
