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
   `ToolSearch(select:WebSearch,WebFetch)`). If one is missing, DECLARE which sub-questions lose
   coverage and proceed with a confidence penalty — never fake a missing source.
1. **Parse** the query into an ordered criteria set (hard / soft / unknown).
   1.5 **Propose the rubric & confirm** (dimensions + source plan + "good" bar) per
   `references/rubric-templates.md`, UNLESS the query already states criteria (then echo + proceed;
   skip the confirm if the user said "just run it").
2. **Route** each sub-question to its purpose-fit source: objective goodness → web critics +
   review-volume; sentiment → X + Reddit + web; precise facts → directed WebFetch.
3. **Wave 1 — discovery.** Dispatch ONE subagent per source IN PARALLEL via the Agent tool. Each
   brief is self-contained: target, fields to extract, the digest contract, "ONLY your source's
   tools", "never fabricate", and an instruction to LOAD ITS PLAYBOOK FIRST (invoke the
   `vox-reddit` / `vox-x` / `vox-web` skill if available, else Read
   `~/.claude/skills/vox-<source>/SKILL.md`). Work non-overlapping tasks while they run; do NOT read
   their transcript files — rely on the returned digest.
4. **Corroborate.** Build a candidate × source matrix; promote only candidates in 2+ channels;
   resolve same-name/duplicate collisions early; label each pick with its corroborating sources.
5. **Wave 2 — verify.** For each finalist, dispatch a narrow stateless verifier to pin facts +
   recent sentiment (two-tier: cheap triage → verified read; disclose which).
6. **Rank** by the user's priority order; but EXECUTE the most-pruning check first.
7. **Render** `references/output-template.md` with per-figure confidence + an auditable scoreboard.
   ALWAYS emit the canonical **Sources that failed / blocked** line (write `none — all fetches
   returned cleanly` when nothing failed) so coverage is explicit and machine-checkable.
8. **Follow-ups = live RE-WEIGHTING**, not restart: re-sort the existing candidate set.
9. **On pushback**, inspect your OWN decomposition for the blind spot, re-measure on any
   user-supplied anchors, and own the miss.

## Hard rules
Cite every claim with a URL. 2+ sources to promote. Never retry a 403/429 (the web subagent
pivots). When data is missing, say so and show the blocked/failed sources. One honest pick, not a
forced winner.
