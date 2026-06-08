# Vox output template

The INVARIANTS below are constant for every answer; the BODY is one of two families. Pick the
skeleton at step 1.5 from the rubric family — **Skeleton A** when the query has rankable finalists
(Places/food, Consumer product), **Skeleton B** when it has no rankable finalist (Media/sentiment,
Company/event, news) — and carry that choice to render. Do not re-decide the shape at the end.

## Shared invariants (EVERY answer, both skeletons)
- **How I built this** — sources used and how each metric/claim was derived (1 short paragraph).
- **Flags / excluded** — each exclusion with the EXACT failing value (over budget, over cap, closed +
  date, single-source-only). Never silently dropped.
- **Sources that failed / blocked** — ALWAYS present. List every source/URL that 403'd, 429'd, was a
  JS-shell, was the wrong entity, or returned no signal, each with its reason. If nothing failed,
  write exactly `none — all fetches returned cleanly`. Never omit this line; an explicit "none" is
  required so coverage is auditable.
- **Bottom line** — one honest synthesis, NOT a forced winner; conditional framing allowed ("if X
  then A; if Z then B").
- **Next actions** — 2–3 concrete offers.

## Skeleton A — ranked (rankable finalists: Places/food, Consumer product)
1. How I built this *(shared)*.
2. **Ranked table** — columns map one-to-one to the rubric dimensions, ordered by the user's stated
   priority. Annotate cells with corroborating-source signals (e.g. "Reddit T1 + X") and confidence
   marks.
3. **How to read it** — prose grouping picks by which dimension each one wins.
4. Flags / excluded · Sources that failed / blocked · Bottom line ("My call") · Next actions *(shared)*.

## Skeleton B — no rankable finalist (sentiment / reception / news: Media/sentiment, Company/event)
1. How I built this *(shared)*.
2. **Core facts** — claim table `Core fact | Finding | Confidence | Sources`. The `Sources` column
   carries the per-claim corroborating sources / channel count (`web+Reddit`, `web-only`). A conflict
   renders here as `⚠️ X vs Y — unverified` — both values, never silently resolved to one.
3. **Sentiment & consensus** — aspect × sentiment carrying each digest's `STRONG / MODERATE /
   SINGLE-SOURCE` consensus-strength label upward; CONSENSUS vs CONTENTION called out.
4. **Themes & dissent** — the recurring takes PLUS the minority / contrarian view; never flattened to
   a false consensus.
5. Flags / excluded · Sources that failed / blocked · Bottom line · Next actions *(shared)*.

## On demand: scoreboard
Per-source tally → deduped distinct total → funnel: surfaced → evaluated → fit → excluded (with
reasons). Show this when the user asks "how thorough was this?" or breadth matters.

## Confidence legend (use consistently, PER FIGURE — never one global hedge)
- `✅` verified (read/corroborated) · `~` or `*` estimate (always footnote the basis) ·
  `⚠️` caution — closure/budget risk OR a conflicting/unverified figure · `❌` excluded.
- **No silent confidence upgrade** — a figure any contributing digest marked `⚠️` / `SINGLE-SOURCE` /
  conflicting MUST keep at least that caution; you may LOWER confidence with justification, but NEVER
  raise it above what the contributing digest reported.
- **Per-claim sources** — tag every promoted fact with its real corroborating sources / channel count
  (`web-only`, `web+Reddit`); a blanket "all 2+ corroborated" is forbidden when any claim is 1-channel.
- Flag single-source numbers and thin samples explicitly (e.g. "4.9/207 — high on quality, lower on
  consistency").
