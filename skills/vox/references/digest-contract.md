# Subagent digest contract

Every Vox source subagent returns EXACTLY this structure so the orchestrator never has to
special-case a source. Never fabricate; an empty result is a valid, explicit envelope.

## Required sections
1. **Source & capability** — which tool/source, and a one-line "what worked / auth status".
2. **Claims table** — markdown table; every row carries an **inline source URL** and a
   confidence mark (`✅` verified · `~` estimate · `⚠️` caution). Columns: `Item | Claim/Detail | Source URL | Confidence`.
3. **Sentiment & consensus** — per item: a sentiment label (Strongly positive / Positive /
   Mixed / Negative) and a **consensus-strength** label (STRONG / MODERATE / SINGLE-SOURCE).
4. **Corroboration notes** — what else (in this source) supports each claim; recurrence counts.
5. **Conflicts / disagreements across fetches** — anywhere two fetches disagree on a value/date/
   figure, or a value looks like a likely extraction error. Record: the claim, value A (URL),
   value B (URL), and which (if either) you believe + why. Empty is fine — state "none".
6. **Estimates labeled** — bullet list of every `~`/estimate value and the basis for it.
7. **Sources that failed (not used)** — URL + reason (403 / 429 / JS-shell / blocked / not-listed /
   wrong-entity). Empty is fine, but state "none". End a line with the tag `needs-browser` when the
   item is important and a real browser could retry it; the orchestrator queues it for `vox-browser`.
8. **Bottom line** — a 1–3 sentence TL;DR for the orchestrator.

## Status
`Status:` one of `ok` · `partial` (some items or sub-questions unserved; list them in section 7) ·
`no-capability` (a required tool is missing or unidentifiable; name it, its install, and the
unserved sub-questions) · `blocked` (the source was reachable but hard-blocked for the whole query) ·
`no-signal` (ran cleanly, found nothing: return sections 1, 7, 8 and say so plainly). Do not invent
items to fill the table.
