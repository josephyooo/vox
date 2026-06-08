---
name: vox
description: Search across Reddit, X, and the web for a ranked, cited, honestly-hedged recommendation or sentiment read on anything — "best running shoes", "how good is the new Claude model", "best ramen near Union Square". Use when the user asks what's best, what people think, or for a cross-source recommendation.
---

# vox — cross-source recommendation & sentiment orchestrator

You orchestrate Reddit + X + web subagents into one ranked, cited answer. Read-only. NEVER
fabricate; degrade honestly. All work runs on the user's subscription.

## References
- Digest each subagent returns: [digest-contract](references/digest-contract.md)
- Final deliverable shape: [output-template](references/output-template.md)
- Query-rubric priors: [rubric-templates](references/rubric-templates.md)

## Loop
0. **Capability-probe** sources you'll use (`reddit-cli --help`, `bird check`,
   `ToolSearch(select:WebSearch,WebFetch)`; for the places tier `maps-cli doctor`; for the browser
   tier `ToolSearch(select:mcp__claude-in-chrome__…)` + `list_connected_browsers`). If an HTTP source
   is missing, DECLARE which sub-questions lose coverage and proceed with a confidence penalty — never
   fake a missing source. The places/browser tier has a stricter rule: see the **Places & browser
   tier** section below.
1. **Parse** the query into an ordered criteria set (hard / soft / unknown).
   1.5 **Propose the rubric & confirm** (dimensions + source plan + "good" bar) per
   `references/rubric-templates.md`, UNLESS the query already states criteria (then echo + proceed;
   skip the confirm if the user said "just run it"). **Record the output skeleton** (A = rankable
   finalists; B = no rankable finalist) as part of the confirmed rubric, by the rule rankable→A /
   else→B; carry it to render (step 7).
2. **Route** each sub-question to its purpose-fit source: objective goodness → web critics +
   review-volume; sentiment → X + Reddit + web; precise facts → directed WebFetch; **place data
   (rating × review-volume / hours / address) → the places tier (`vox-maps`, primary, parallel);
   logistics / transit detours / "detour with a stop" → the browser tier (`vox-browser`, Maps
   directions); general-search gaps + bot-blocked-but-important reads → the browser tier (Google)**.
   Mark which sub-questions NEED the places tier or browser tier (drives the Places-tier gate below). **Video collections / playlists /
   explicit video-URL lists → the video tier (`vox-video`)**, which ingests each video and surfaces
   candidate places for the other sources to corroborate (drives the Video-tier gate below).
3. **Wave 1 — discovery.** Dispatch ONE subagent per source IN PARALLEL via the Agent tool. NOTE:
   `vox-reddit`/`vox-x`/`vox-web`/`vox-browser` are SKILLS, not registered agent types — dispatch
   each as `subagent_type: general-purpose` (or `Explore`) and tell it to invoke its `vox-<source>`
   skill as its FIRST action; never pass `subagent_type: vox-reddit/…` (it errors "Agent type not
   found"). Each
   brief is self-contained: target, fields to extract, the digest contract, "ONLY your source's
   tools", "never fabricate", and an instruction to LOAD ITS PLAYBOOK FIRST (invoke the
   `vox-reddit` / `vox-x` / `vox-web` skill if available, else Read
   `~/.claude/skills/vox-<source>/SKILL.md`). Work non-overlapping tasks while they run; do NOT read
   their transcript files — rely on the returned digest. When a PLACES/LOGISTICS sub-question is
   NEEDED and the browser tier is available, ALSO dispatch exactly ONE `vox-browser` agent in this
   wave (it loads `vox-browser`/SKILL.md, owns Chrome, works its queued sub-questions SERIALLY),
   concurrent with the stateless three. Bot-blocked reads discovered by `vox-web` during this wave
   are handled by the SAME single agent in a post-Wave-1 follow-up (see **Places & browser tier**). Never run
   more than one browser agent.
   When PLACE-DATA sub-questions are NEEDED and the places tier is available (`maps-cli doctor` ok),
   dispatch `vox-maps` in Wave 1 as a STATELESS source (like the HTTP three — it owns no shared
   resource, so it runs in parallel and may process multiple finalists concurrently); it loads
   `vox-maps`/SKILL.md and calls `maps-cli places`. Dispatch it as `subagent_type: general-purpose`
   (it is a SKILL, not an agent type). Any place sub-question it returns `no-capability` or blocked
   (exit 3) for → escalate THAT sub-question to the single `vox-browser` agent.
   When the INPUT is a TikTok collection / playlist / video-URL list, `vox-video` is the Wave-1
   **discovery driver**: dispatch exactly ONE `vox-video` agent (it loads `vox-video`/SKILL.md and
   runs its two-phase ingest→extract; it REQUIRES `mw` + `ffmpeg` + `tiktok-cli`). Treat its surfaced
   entities as the candidate set the stateless three + browser then corroborate (steps 4–5).
   `vox-video` uses tiktok-cli's own headless Playwright — a SEPARATE browser from `vox-browser`'s
   Chrome — so it never contends with the browser tier. Never run more than one `vox-video` agent.
4. **Corroborate.** Build a candidate × source matrix; promote only candidates in 2+ channels;
   resolve same-name/duplicate collisions early; label each pick with its corroborating sources.
5. **Wave 2 — verify (finalist OR contested claim).**
   - **Per-finalist (Skeleton A):** for each finalist, dispatch a narrow stateless verifier to pin
     facts + recent sentiment (two-tier: cheap triage → verified read; disclose which).
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
6. **Rank** by the user's priority order; but EXECUTE the most-pruning check first.
7. **Render** `references/output-template.md` with per-figure confidence + an auditable scoreboard.
   For video-tier runs, add a **video-provenance** column (video URL + timestamp/frame, creator + COI,
   engagement) and list ingest failures (empty transcripts, unresolved entities, rate-limited comments)
   in the "Sources that failed / blocked" line.
   ALWAYS emit the canonical **Sources that failed / blocked** line (write `none — all fetches
   returned cleanly` when nothing failed) so coverage is explicit and machine-checkable.
   **Citation-completeness gate (before emitting):** carry every permalink forward from the subagent
   digests — every quoted string AND every standalone number/proportion/score in the final answer
   MUST sit next to an inline markdown link. A bare platform name (`(Reddit)`, plain `r/television`)
   or a floating score is NOT a citation. Self-check: scan the draft for quotation marks and numeric/
   `%` figures and confirm each is adjacent to a link; if a quote can't be linked, drop the quotation
   marks and present it as an unattributed paraphrase.
8. **Follow-ups = live RE-WEIGHTING**, not restart: re-sort the existing candidate set.
9. **On pushback**, inspect your OWN decomposition for the blind spot, re-measure on any
   user-supplied anchors, and own the miss.

## Places & browser tier (places-first via gosom; browser = logistics + fallback; halt-by-default)
Place DATA (rating × review-volume / hours / address) is served by the **places tier**, available if
**`vox-maps` (gosom — `maps-cli doctor` exits 0) OR Chrome** is available. The browser is still a
SINGLE shared resource — exactly one `vox-browser` agent, ever; never parallel — and it now owns
**logistics/transit** and serves as the **place-data fallback**. There are THREE triggers for browser
work:
- **(a-data) Place data `vox-maps` could not serve** — a finalist it returned `no-capability` or
  blocked (exit 3) for. Escalate that sub-question to the one `vox-browser` agent.
- **(a-logistics) Logistics / transit detours** — known at routing (step 2); gosom has no directions,
  so these always go to `vox-browser`. Dispatch the one browser agent in Wave 1 when logistics is
  needed.
- **(b) Bot-blocked-but-important reads** — discovered DURING Wave 1 by `vox-web`, which tags such
  URLs `needs-browser` in its digest's "sources that failed" block. After Wave 1, the SAME single
  browser agent reads them in a brief follow-up pass.

Availability gate (keyed off the routing-time PLACE / LOGISTICS need):
- **Place data needed + `vox-maps` available (`maps-cli doctor` ok)** → dispatch `vox-maps` in Wave 1
  (stateless, parallel). Escalate ONLY the finalists it returns `no-capability`/blocked for to the one
  `vox-browser` agent (when Chrome is up).
- **Place data needed + `vox-maps` UNavailable (exit 4) + Chrome available** → `vox-browser` serves the
  place data (its Maps playbook), as the fallback.
- **Logistics needed** → always `vox-browser` (one agent, Wave 1), independent of gosom.
- **Not needed** → ignore both tiers; run the HTTP tier as normal.
- **Place / logistics needed + BOTH gosom and Chrome UNavailable, default** → **HALT-AND-REPORT.** Do
  NOT silently produce a web-only answer. State which sub-questions depend on the places/browser tier,
  that neither gosom nor Chrome is available, and the two ways forward: (a) pair Chrome / install gosom
  and re-ask, or (b) re-run with `--web-fallback`.
- **… + `--web-fallback`** (literal flag OR natural language like "proceed web-only if neither's up")
  → fall those sub-questions back to `vox-web`; mark every figure that lost places/browser
  corroboration with a LOWER-confidence mark + a one-line "no places/browser coverage" note.
A late `needs-browser` escalation (trigger b) that can't be served because Chrome is unavailable is
NOT a hard halt — `vox-web` already disclosed the gap; note it and move on. A `vox-maps` or
`vox-browser` agent that returns no usable digest (orphaned/dead) counts as UNavailable for its
sub-questions.

## Video tier (collection analyzer; halt-by-default on missing prereqs)
Triggered when the input is a TikTok collection / playlist / video-URL list (not a plain topic
query). `vox-video` is the candidate-discovery driver: it ingests each video (download → `mw`
transcript → `ffmpeg` frames/vision → comments), extracts place claims under the five honesty rules,
and returns the digest; the stateless sources + browser then corroborate its candidates.
- **Prereqs REQUIRED** (this tier requires local ASR): `mw`, `ffmpeg`, `tiktok-cli` (+ resolvable
  ms_token). If any is missing → **HALT-AND-REPORT** the missing tool + its install; do NOT produce a
  partial answer (there is no `--web-fallback` for video — the videos ARE the source).
- **Single video agent**: exactly one `vox-video`, ever. It owns tiktok-cli's headless Playwright,
  independent of `vox-browser`'s real Chrome (no contention).
- **Heavy / resumable**: ingest is cached; follow-ups re-weight the candidate set without re-downloading.
- **No phantom quotes**: a video whose transcript came back empty contributes on-screen/caption claims
  only — never a spoken quote.

## Hard rules
Cite every claim with a URL. 2+ sources to promote. Never retry a 403/429 (the web subagent
pivots). When data is missing, say so and show the blocked/failed sources. One honest pick, not a
forced winner.
