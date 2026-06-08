# Vox no-finalist read hardening — design

**Date:** 2026-06-08
**Repo:** vox (single repo; prose-skill change + contract tests + eval goldens)
**Status:** design approved; ready for implementation plan

## Problem

Vox's pipeline is **finalist-shaped**: the output template is a single ranked-candidate table,
Wave-2 verification is keyed "for each finalist", and the rubric families name outputs
("CONSENSUS vs CONTENTION", "balanced brief") that have no skeleton to render into. This degrades
on **sentiment / news / reception** queries that have *no rankable finalist* — and it keeps biting.

A 41-agent review of the two unchecked real vox runs (`88fb1431` "MARTA shooting in atl"; `8b863380`
"obsession … critic and fan analysis of the ending") found the SAME deferral cluster firing on BOTH
runs, plus one genuine **correctness failure**:

- On MARTA, vox's own web digest flagged a date conflict ("one fetch placed the stabbings March
  24/30 — likely an extraction error vs May 30/31"), yet the orchestrator declared "no Wave 2
  verifier is needed — corroboration is already 2+ channels on every key fact" and shipped the
  conflicted date as a confident, unmarked bullet. A later re-run silently corrected it. Root cause:
  step 5 is finalist-only, so a no-finalist news query had no rule forcing verification of a
  self-disclosed conflict, and the digest had nowhere to even record the conflict.
- The Obsession run invented its own headings and produced **structurally different shapes on two
  runs of the same query**; it also laundered a named-person quote through an unread aggregator
  ("AwardsWatch's McQuade called it '…' (via MovieWeb)") and asserted a bare corroboration count
  ("~6 outlets", 4 links, one of them a 403'd snippet).

## Goal

Add a second output skeleton for no-finalist reads, make conflict handling a first-class path
(record → recheck-once → disclose honestly), and tighten the step-7 citation gate so it checks
*provenance*, not just link *adjacency*. One coherent pass.

## Scope

**In:** the no-finalist read path (review items 1.1–1.5) **plus** the two step-7 honesty items
(2.1 quote-provenance, 2.2 corroboration-count) — they hit the same gate and 2.2 mechanically
overlaps 1.4's per-claim channel-count tag.

**Out (explicit YAGNI guard):** NO new rubric families. Item 1.3 is only *wiring existing* families
to skeletons. The Tier-3 "breaking news / single event" and "just-released media reception" families
are deferred and NOT part of this spec. Tier-4 polish items are out. The dropped "cross-run X-only
top-up" idea is out (it presumes a persisted HTTP candidate set that does not exist).

## Architecture

Two output skeletons instead of one. The choice is made **early** — at step 1.5, when the rubric
family is picked — and recorded as part of the confirmed rubric, then used at render (step 7). This
is the key change: both audited runs improvised the shape at the end; the skeleton is now a decision,
not an improvisation.

**Skeleton selection rule (drives everything):**
- **Skeleton A (ranked)** — the query resolves to a set of *comparable candidate entities you rank*
  (Places/food, Consumer product). This is today's existing template, renamed; behavior unchanged.
- **Skeleton B (no rankable finalist)** — the query is "what do people think / what happened / how is
  X received" with nothing to rank (Media/sentiment, Company/event, news).

Conflict handling is a first-class path present in BOTH skeletons: a disagreement across fetches now
has (a) a place to live in the digest, (b) a trigger that forces a cheap recheck, (c) an honest
render when it can't be resolved.

## Files changed (6)

### 1. `skills/vox/references/output-template.md`

Restructure into **shared invariants + two bodies** (factor the common sections out once; do not
duplicate them per skeleton):

- **Intro:** the INVARIANTS are constant; the BODY is one of two families. Pick the skeleton at step
  1.5 from the rubric family (A = rankable finalists, B = no rankable finalist). (Replaces today's
  "the SHAPE is constant".)
- **`## Shared invariants` (every answer, both skeletons):** How I built this · Flags / excluded ·
  Sources that failed / blocked (ALWAYS present; explicit `none — all fetches returned cleanly`) ·
  Bottom line (one honest synthesis, NOT a forced winner; conditional framing allowed) · Next actions.
- **`## Skeleton A — ranked` (Places/food, Consumer product):** body = Ranked table (columns = rubric
  dimensions, ordered by stated priority, cells annotated with corroborating-source signals +
  confidence marks) → How to read it. Unchanged from today.
- **`## Skeleton B — no rankable finalist` (Media/sentiment, Company/event, news):** body =
  1. **Core facts** — claim table `Core fact | Finding | Confidence | Sources`. The `Sources` column
     carries the per-claim corroborating sources / channel count (`web+Reddit`, `web-only`). A conflict
     renders here as `⚠️ X vs Y — unverified`, never silently resolved to one value.
  2. **Sentiment & consensus** — carries the digests' `STRONG / MODERATE / SINGLE-SOURCE` labels
     upward as aspect × sentiment with CONSENSUS vs CONTENTION.
  3. **Themes & dissent** — recurring takes PLUS the minority/contrarian view; never flattened to a
     false consensus.
- **`## On demand: scoreboard`** — unchanged.
- **`## Confidence legend`** — broaden `⚠️` from "caution (closure/budget risk)" → "caution:
  closure/budget risk OR conflicting/unverified figure". Add the two carry-forward rules so the legend
  documents them where figures are marked: no silent confidence upgrade; per-claim channel count.

### 2. `skills/vox/references/digest-contract.md`

Add one required section (place it right after "Corroboration notes" — the flip side, agreement vs
disagreement; renumber the subsequent sections):

> **Conflicts / disagreements across fetches** — anywhere two fetches disagree on a value/date/figure,
> or a value looks like a likely extraction error. Record: the claim, value A (URL), value B (URL),
> and which (if either) you believe + why. Empty is fine — state "none".

This is the slot the MARTA date-conflict had nowhere to go into.

### 3. `skills/vox/references/rubric-templates.md`

Each family names its skeleton; the Behavior block records the choice:
- Places / food → `Output: Skeleton A — ranked venue table`
- Consumer product → `Output: Skeleton A — ranked model table`
- Media / model sentiment → `Output: Skeleton B` (keep the aspect dimensions; the loose "CONSENSUS vs
  CONTENTION" prose now points at Skeleton B's body)
- Company / event → `Output: Skeleton B` (replaces the undefined "balanced brief")
- **Behavior** block gains: *record the chosen skeleton (A/B) as part of the confirmed rubric, so
  render uses it rather than re-deciding. The skeleton is chosen by the universal selection rule
  (rankable finalists → A, else → B), so a synthesized-from-scratch rubric or a query that fits no
  named family (e.g. breaking news → closest is Company/event, or synthesized) still picks a skeleton.*

### 4. `skills/vox/SKILL.md`

- **Step 1.5** — when confirming the rubric, record the chosen skeleton (A/B) per the family.
- **Step 5 — rewrite from finalist-only to finalist OR contested-claim:**
  - Per-finalist verifier (Skeleton A) — unchanged.
  - **Conflict trigger (both skeletons, MANDATORY):** if any digest's Conflicts slot is non-empty, or
    a high-stakes claim (event date, toll, who/what/where) is contested or self-flagged a likely
    extraction error, you MUST resolve it before render — EVEN IF headline facts already corroborate
    2+ channels. The 2+-channel rule PROMOTES a candidate; it does NOT clear a conflicting figure.
    Resolve cheaply: ONE narrow re-fetch of just that fact (orchestrator's own WebFetch/WebSearch;
    escalate to a directed `vox-web` verifier only if the re-fetch is itself blocked).
  - **No-finalist branch (Skeleton B):** no per-finalist wave — instead a lightweight corroboration
    pass: every load-bearing claim/number is in 2+ channels OR carries a single-source hedge, and each
    contested fact gets the one narrow re-fetch. State in your reasoning that the per-finalist wave was
    intentionally skipped and why.
  - **Unresolved → disclose, don't pick:** if the re-fetch can't resolve it, render BOTH values with
    `⚠️ (sources disagree: X vs Y — unverified)`. Never silently choose one; the phrase "corroborated
    on every key fact" is FORBIDDEN while any conflict is open.
- **Step 7 — extend the existing citation-completeness gate** (keep today's adjacency rule) with four
  rules, run as pre-emit self-checks (no new agents):
  1. **No silent confidence upgrade:** a fact any contributing digest marked `⚠️`/`SINGLE-SOURCE`/
     conflicting MUST retain at least that caution; you may LOWER confidence with justification but
     NEVER raise it above what the contributing digest reported.
  2. **Per-claim source count:** tag each promoted fact with its real corroborating sources / channel
     count (`web-only`, `web+Reddit`) — Skeleton B's `Sources` column, Skeleton A's cell annotation. A
     blanket "all 2+" is forbidden when any claim is 1-channel.
  3. **Quote provenance:** a quote attributed to a NAMED person/outlet must link the page where it was
     actually READ; if recovered via an aggregator that re-quotes, strip the quote marks and tag
     `[paraphrase via <aggregator>]`, or drop it — never render an aggregator re-quote as verbatim
     attribution to the original.
  4. **Corroboration count links all N:** any count/strength claim ("N outlets", "genuine consensus")
     must inline-link EVERY counted source, or downgrade to a non-numeric hedge ("multiple critics"); a
     snippet-only/403'd source may NOT be tallied into N.

### 5. `tests/test_no_finalist_read.py` (new)

Concept-word contract assertions (key on stable words, not exact sentences — match the
`test_routing.py` / `test_video_agy.py` style) that the prose documents:
- two skeletons exist (Skeleton A / Skeleton B) in `output-template.md`;
- Skeleton B's three body sections (core facts + `Sources` column, sentiment & consensus, themes & dissent);
- the digest **Conflicts / disagreements** slot in `digest-contract.md`;
- step-5 **conflict trigger** + **no-finalist branch** + the "2+ promotes but does not clear a
  conflict" rule + "disagree … unverified" disclose-don't-pick;
- the four step-7 rules (no-upgrade, channel-count, quote-provenance/paraphrase-via, count-links-all-N);
- the broadened `⚠️` (conflicting/unverified);
- each rubric family names a skeleton (A/B) in `rubric-templates.md`.

### 6. `eval/goldens/`

- Update `claude-model-sentiment.md` expectations to reference Skeleton B (sentiment & consensus body,
  themes & dissent, no forced winner).
- Add one new golden — a breaking-news / event read carrying a cross-source date/figure conflict —
  whose expectations assert: Skeleton B shape; the conflict is RESOLVED by recheck or DISCLOSED with
  `⚠️` (both values), never silently picked; channel counts tagged; no quote laundering.

## Data flow

1. **Step 1.5:** orchestrator picks the rubric family → picks Skeleton A or B → records it in the
   confirmed rubric.
2. **Wave 1:** each source subagent returns the digest, now including a "Conflicts / disagreements"
   section (often "none").
3. **Corroborate (step 4):** 2+ channels promotes a candidate/claim.
4. **Step 5:** if any digest Conflicts slot is non-empty or a high-stakes claim is contested → one
   narrow recheck. Skeleton B runs the lightweight no-finalist corroboration pass instead of a
   per-finalist wave.
5. **Step 7 render:** emit the recorded skeleton; run the citation + four honesty self-checks;
   unresolved conflicts render with `⚠️` and both values.

## Error handling / edge cases

- **Recheck blocked:** the narrow re-fetch 403s/429s → escalate to a directed `vox-web` verifier; if
  still unresolved → disclose both with `⚠️`. Never retry a 403/429 (existing hard rule).
- **No conflicts at all:** the Conflicts slot is "none"; step 5's conflict trigger is a no-op; Skeleton
  B still runs its lightweight corroboration pass.
- **A query that looks borderline rankable:** default to the family's skeleton; if genuinely mixed
  (a recommendation that also wants sentiment context), Skeleton A may carry a short sentiment note,
  but the conflict + honesty rules apply regardless of skeleton.
- **Single-source load-bearing claim (Skeleton B):** kept with an explicit single-source hedge +
  1-channel tag, never promoted to a blanket "corroborated".

## Success criteria

- A no-finalist sentiment/news query renders Skeleton B (stable shape across re-runs), not a forced
  ranked table.
- A digest-disclosed conflict can no longer ship unverified and unmarked: it is either resolved by a
  recheck or rendered with `⚠️` + both values.
- An aggregator re-quote can no longer be presented as a verbatim named attribution; an "N outlets"
  count must link all N.
- A 1-channel claim cannot hide inside a blanket "2+ corroborated"; confidence is never silently
  upgraded above what a digest reported.
- Gate green: `pytest`, `ruff check tools tests eval`, `validate_skills.py skills` (`[ok]` per skill).

## Out of scope (restated)

New rubric families (breaking-news, just-released-media); Tier-4 polish (rounding volatile engagement
counts, source-centrality-scaled penalties, snippet `~approximate` state); the cross-run X-only
top-up. Discoverability of vox for places/sentiment queries is an observation, not a code change.
