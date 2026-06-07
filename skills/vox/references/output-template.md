# Vox output template

A fixed skeleton; the table's DIMENSIONS swap per query family (see rubric-templates.md), the
SHAPE is constant.

## Skeleton
1. **How I built this** — sources used and how each metric was derived (1 short paragraph).
2. **Ranked table** — columns map one-to-one to the rubric dimensions, ordered by the user's
   stated priority. Annotate cells with corroborating-source signals (e.g. "Reddit T1 + X") and
   confidence marks.
3. **How to read it** — prose grouping picks by which dimension each one wins.
4. **Flags / excluded** — each exclusion with the EXACT failing value (over budget, over cap,
   closed + date, single-source-only). Never silently dropped.
5. **My call** — one honest recommendation; conditional framing allowed ("if X then A; if Z then B").
6. **Next actions** — 2–3 concrete offers.

## On demand: scoreboard
Per-source tally → deduped distinct total → funnel: surfaced → evaluated → fit → excluded (with
reasons). Show this when the user asks "how thorough was this?" or breadth matters.

## Confidence legend (use consistently, PER FIGURE — never one global hedge)
- `✅` verified (read/corroborated) · `~` or `*` estimate (always footnote the basis) ·
  `⚠️` caution (closure/budget risk) · `❌` excluded.
Flag single-source numbers and thin samples explicitly (e.g. "4.9/207 — high on quality,
lower on consistency").
