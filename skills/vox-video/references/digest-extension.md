# Video digest extension

`vox-video` returns the standard 7-section [digest contract](../../vox/references/digest-contract.md).
This file says how video-only signals populate those sections — and the five rules that keep it
honest. The orchestrator ingests the SAME 7 sections; video just makes them richer.

## How video signals map onto the digest
- **Claims table** — each row's source URL is the **video URL with a timestamp/frame** (`…/video/<id>`
  `@0:47` for spoken; `frame f3_50pct` for on-screen). Confidence mark is **capped by signal source**
  (Rule 1). One row per claim atom (price / dish / verdict / logistics), not one prose blob per place.
- **Sentiment & consensus** — creator sentiment and **comment-crowd sentiment are separate**;
  consensus-strength uses cross-video `mention_count` (3 videos by 3 creators = STRONG; 1 = SINGLE-SOURCE).
- **Corroboration notes** — carry the video-native fields: **engagement** (views/likes/saves as a
  popularity proxy), **creator + COI** (organic/sponsored/comped/affiliate), **recency** (upload date;
  flag stale claims).
- **Estimates labeled** — caption/on-screen-derived figures are `~` until verified; band-vs-verified
  prices follow the same rule the maps playbook uses.
- **Sources that failed** — list ingest failures explicitly: empty-transcript videos (by id),
  unresolved/garbled entities, rate-limited comments (`none_fetched` ≠ neutral), un-enumerated items.

## The five honesty rules (each fixes a documented failure of the inspiration run)
1. **Signal-priority confidence** — transcript (spoken) > on-screen > caption; comments are a separate
   crowd channel, never merged into the creator's claim. A claim's confidence is capped by its source.
2. **No phantom quotes** — a transcript-sourced (spoken) claim may exist ONLY if that video's
   transcript status is `ok`. Empty-audio videos still contribute on-screen/caption claims, labeled.
3. **Every claim carries a URL** (+ timestamp/frame when spoken/on-screen) — traceability to the moment.
4. **Engagement & recency are fields, not afterthoughts** — used as ranking inputs/tie-breakers; stale
   claims flagged from the upload date.
5. **"No data" ≠ "neutral"** — record coverage (e.g. `comments: none_fetched`) so silence is never
   read as consensus.
