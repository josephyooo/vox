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
5. **Estimates labeled** — bullet list of every `~`/estimate value and the basis for it.
6. **Sources that failed (not used)** — URL + reason (403 / 429 / JS-shell / not-listed /
   wrong-entity). Empty is fine, but state "none".
7. **Bottom line** — a 1–3 sentence TL;DR for the orchestrator.

## Status
If the source yielded nothing, return sections 1, 6, 7 with **Status: no-signal** and say so
plainly. Do not invent items to fill the table.
