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
   `ToolSearch(select:WebSearch,WebFetch)`; for the browser tier
   `ToolSearch(select:mcp__claude-in-chrome__…)` + `list_connected_browsers`). If an HTTP source is
   missing, DECLARE which sub-questions lose coverage and proceed with a confidence penalty — never
   fake a missing source. The browser tier has a stricter rule: see the **Browser tier** section below.
1. **Parse** the query into an ordered criteria set (hard / soft / unknown).
   1.5 **Propose the rubric & confirm** (dimensions + source plan + "good" bar) per
   `references/rubric-templates.md`, UNLESS the query already states criteria (then echo + proceed;
   skip the confirm if the user said "just run it").
2. **Route** each sub-question to its purpose-fit source: objective goodness → web critics +
   review-volume; sentiment → X + Reddit + web; precise facts → directed WebFetch; **places /
   ratings × review-volume / hours / transit-logistics → the browser tier (Maps); general-search
   gaps + bot-blocked-but-important reads → the browser tier (Google)**. Mark which sub-questions
   NEED the browser tier (drives the Browser-tier gate below). **Video collections / playlists /
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
   are handled by the SAME single agent in a post-Wave-1 follow-up (see **Browser tier**). Never run
   more than one browser agent.
   When the INPUT is a TikTok collection / playlist / video-URL list, `vox-video` is the Wave-1
   **discovery driver**: dispatch exactly ONE `vox-video` agent (it loads `vox-video`/SKILL.md and
   runs its two-phase ingest→extract; it REQUIRES `mw` + `ffmpeg` + `tiktok-cli`). Treat its surfaced
   entities as the candidate set the stateless three + browser then corroborate (steps 4–5).
   `vox-video` uses tiktok-cli's own headless Playwright — a SEPARATE browser from `vox-browser`'s
   Chrome — so it never contends with the browser tier. Never run more than one `vox-video` agent.
4. **Corroborate.** Build a candidate × source matrix; promote only candidates in 2+ channels;
   resolve same-name/duplicate collisions early; label each pick with its corroborating sources.
5. **Wave 2 — verify.** For each finalist, dispatch a narrow stateless verifier to pin facts +
   recent sentiment (two-tier: cheap triage → verified read; disclose which).
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

## Browser tier (single serial owner; halt-by-default)
The browser is a SINGLE shared resource — exactly one `vox-browser` agent, ever; never parallel,
never a second concurrent one. There are TWO triggers for browser work:
- **(a) Places/logistics** — known at routing (step 2). Dispatch the one browser agent in Wave 1,
  concurrent with the stateless three.
- **(b) Bot-blocked-but-important reads** — discovered DURING Wave 1 by `vox-web`, which tags such
  URLs `needs-browser` in its digest's "sources that failed" block. After Wave 1, collect those tags
  and have the SAME single browser agent read them in a brief follow-up pass.

Availability gate (keyed off the routing-time need, i.e. trigger (a)):
- **Needed + available** → dispatch the one browser agent (Wave 1 for places; follow-up for queued
  `needs-browser` URLs).
- **Not needed** → ignore the browser entirely; run the HTTP tier as normal (no halt regardless of
  Chrome).
- **Needed + UNavailable (Chrome can't connect), default** → **HALT-AND-REPORT.** Do NOT silently
  produce a web-only answer. State which sub-questions/criteria depend on the browser, that Chrome
  isn't connected, and the two ways forward: (a) pair Chrome and re-ask, or (b) re-run with
  `--web-fallback`.
- **Needed + UNavailable + `--web-fallback`** (literal flag OR natural language like "proceed
  web-only if Chrome's down") → fall the browser sub-questions back to `vox-web`; mark every figure
  that lost browser corroboration with a LOWER-confidence mark + a one-line "no browser coverage" note.
A late `needs-browser` escalation (trigger b) that can't be served because Chrome is unavailable is
NOT a hard halt — `vox-web` already disclosed the gap; note it and move on. A `vox-browser` agent
that returns no usable digest (orphaned/dead) counts as UNavailable for its sub-questions.

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
