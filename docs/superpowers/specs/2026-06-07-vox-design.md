# Vox — Design Spec

**Date:** 2026-06-07
**Status:** Approved (design) — pending implementation plan
**Working name:** Vox ("voice of the crowd")
**Provenance:** Grounded in 187 patterns mined from prior real Claude sessions that did
multi-source recommendation/sentiment work. See [`../vox-recipe.md`](../vox-recipe.md).

## 1. Purpose

Vox answers *"what's the best / what do people actually think about X?"* by searching across
several independent sources, cross-checking them, and synthesizing a **ranked, cited,
honestly-hedged** answer — for anything from "best running shoes for flat feet" to "how good is
the new Claude model" to "best ramen near Union Square."

It is **read-only**, **never fabricates**, and runs **entirely on the user's Claude
subscription** (no API billing). It is built as a **Claude Code skill system**: an orchestrator
skill that drives per-source subagent skills.

## 2. Goals & Non-Goals

### Goals
- Turn a vague question into a ranked, cited answer with **per-figure confidence**.
- Route each sub-question to the source best suited to answer it; **corroborate across sources**.
- **Never fabricate.** Degrade honestly when a source is blocked or evidence is thin.
- Subscription-native (runs interactively inside Claude Code), no API calls.
- **Rigor via an eval harness** (golden queries + LLM judge), since prompts aren't unit-testable.

### Non-Goals (v1)
- Browser-driven sources (Google, Google Maps) — **Phase 2** (the "browser tier").
- TikTok / Instagram — **later**, evidence-gated (zero mined evidence they work as text sources).
- Shell invocation (`vox "..."` from a terminal) — **later**, via `claude-session-driver` (`csd`).
- Posting/writing anywhere — Vox is strictly read-only.
- Aggressive anti-bot bypass — v1 is **polite degradation** + an opt-in third-party reader (Jina).

## 3. Decisions

| Decision | Choice |
|---|---|
| Name | **Vox** (command surface `/vox`) |
| First slice | **Text/sentiment-first**: Reddit + X + Web |
| Architecture | **Skill system (A)** — orchestrator skill + per-source subagent skills |
| Billing | **Subscription only** (interactive Claude Code); no API, no `claude -p` |
| Sources (v1) | `vox-reddit` (`reddit-cli`), `vox-x` (`bird`), `vox-web` (`WebSearch`/Brave + `WebFetch` + Jina rung) |
| Runtime query rubric | **Template priors + propose-and-confirm** (Step 1.5) |
| Rigor | **Eval harness**: golden queries + LLM-judge rubric loop + live source smokes |
| Shell layer | **Adopt `obra/claude-session-driver`** later; do not build a runner |
| Browser tier | **Phase 2** — `vox-google` + `vox-maps` (Claude-in-Chrome, orchestrator-driven) |

## 4. Architecture & repository

A thin, declarative **skill system**. No new fetching code is needed for v1: `reddit-cli` and
`bird` already exist, and `WebSearch`/`WebFetch` are built-in Claude Code tools. The per-source
"skills" are **playbook contracts** (how to drive a source well + the fixed digest to return),
authored as Claude Code skills so they're modular and independently editable/gradable.

```
vox/
  install.sh                      # symlink skills/* into ~/.claude/skills/
  skills/
    vox/                          # orchestrator skill (the brain)
      SKILL.md
      references/
        rubric-templates.md       # per-family query-rubric priors
        output-template.md        # the fixed deliverable skeleton + confidence legend
        digest-contract.md        # the envelope every subagent must return
    vox-reddit/SKILL.md           # reddit-cli playbook
    vox-x/SKILL.md                # bird playbook
    vox-web/
      SKILL.md                    # WebSearch/WebFetch playbook
      references/
        source-ladder.md          # most→least fetchable source order
        antibot-ladder.md         # 403/JS-shell map + pivot order + Jina rung
  eval/
    goldens/                      # golden query cases (input + expectations)
    judge-rubric.md               # how we grade a Vox run
    run-eval.md                   # how to execute the eval loop
  docs/
    vox-recipe.md                 # the 187-finding mined recipe (source of truth)
    superpowers/specs/2026-06-07-vox-design.md
```

**Invocation.** Primary: `/vox <query>`. The orchestrator skill's description also lets it
auto-activate on natural asks ("what do people think of X", "best Y for Z"). Because it's a
skill running inside the user's Claude Code session, all work — including dispatched subagents —
bills the **subscription**.

**Subagent loading.** The orchestrator dispatches one subagent per source via the `Agent` tool
(parallel; all v1 sources are stateless). The brief is a **thin task spec** (target, fields to
extract, output schema, "never fabricate"); it instructs the subagent to **load its playbook**
first — via the `Skill` tool if available to subagents, otherwise by `Read`-ing the installed
playbook file (`~/.claude/skills/vox-<source>/SKILL.md`). Separation of concerns: the
orchestrator owns *what*; the source skill owns *how*.

## 5. Components

### 5.1 Orchestrator skill (`vox`)
The brain. Encodes the orchestration loop (§6), owns the rubric system (§7), the corroboration
gate and ranking (§9), the output template (§8), the running scoreboard, and the conversational
moves (live re-weighting on follow-ups; self-diagnosis on pushback).

### 5.2 Per-source subagent skills
Each is a self-contained playbook (the recipe's §2 contract):
- **`vox-reddit`** — `reddit-cli` (scoped `-r <sub> -s relevance`; drill top-comment threads;
  rank by cross-thread recurrence; flag splits; never command-substitute post IDs).
- **`vox-x`** — `bird` (`bird check` first; two-stage broad→named queries; helper-script JSON
  parsing; rank by independent-user count; flag closures; report zero-results honestly).
- **`vox-web`** — `WebSearch` (Brave) + `WebFetch`: `ToolSearch(select:WebSearch,WebFetch)`
  first; parallelize 2–4 calls/turn; mine result-page **titles/snippets** as first-class data;
  the source ladder; the anti-bot ladder incl. the **Jina rung**; directive extraction prompts.

### 5.3 The digest contract (uniform across sources)
Every subagent returns the same envelope so the orchestrator never special-cases a source:
1. One-line entity/claim classification.
2. A claims table — each row carries an **inline source URL** and a confidence mark.
3. Sentiment + **consensus-strength** label.
4. What corroborated it (which other signals/sources).
5. An **"estimates labeled"** block (`~`/`est` items with their basis).
6. A **"sources that failed (not used)"** block (URL + reason: 403 / JS-shell / not-listed).
7. A **bottom-line TL;DR** for the orchestrator.
An **empty result is a valid, explicit envelope** (`status: no-signal`), never a silent blank.

## 6. Orchestration loop (text-first)

Adapted from the recipe's 10-step flow; v1 has no stateful/browser resource, so it is pure
parallel fan-out.

0. **Capability-probe** every named source before planning (`reddit-cli --help`, `bird check`,
   `ToolSearch` for web tools). If a source is missing, **declare which sub-questions lose
   coverage** and proceed with a confidence penalty — never fabricate a missing source.
1. **Parse** the query into an ordered criteria set; classify each criterion hard / soft / unknown.
   1.5 **Propose the rubric and confirm** (§7) — dimensions, source plan, "good" thresholds —
   unless the query already states its criteria (then echo the inferred rubric and proceed;
   skippable with a "just run it" intent).
2. **Route** each sub-question to its purpose-fit source (§9 routing table). One subagent per source.
3. **Wave 1 — discovery.** Launch all source subagents in parallel (stateless), each with a
   strict, self-contained brief; the orchestrator works non-overlapping tasks while they run and
   **never reads subagent transcript files** (it relies on the returned digest).
4. **Collect digests → cross-source corroboration.** Build a candidate × source matrix; a
   candidate needs **2+ independent channels** to be promoted; resolve homonyms/duplicates early.
5. **Wave 2 — deep verify.** For each shortlisted candidate, a narrow stateless verifier pins
   exact facts and recent sentiment (two-tier: cheap triage signal → expensive verified read,
   disclosing which is which).
6. **Rank** by the user's stated priority order, but **execute** the most-pruning check first.
7. **Render** the fixed template (§8) with per-figure confidence and the auditable scoreboard.
8. **Follow-ups = live re-weighting**, not a restart: re-sort the existing candidate set when a
   constraint changes or a new axis appears.
9. **Self-diagnose on pushback**: if challenged, inspect Vox's own decomposition for the blind
   spot, re-run the identical measurement on any user-supplied anchors, and own the miss.

## 7. Runtime query rubric (template priors + propose-and-confirm)

Vox builds a per-query **rubric** before Wave 1: the dimensions it will rank on, the source plan,
and the bar for "good." It uses **template priors** as starting points and **confirms with the
user** when the query is under-specified.

Template families (priors — defaults that get adapted, not rigid forms):
- **Places / food** → rating × review-volume, sentiment, value, [logistics if geo]; weight
  Reddit + Maps(P2) + web critics; output = ranked venue table.
- **Consumer product** ("best running shoes") → the attributes that matter (e.g. cushioning,
  support, durability, price); weight Reddit (niche subs) + review sites + X; output = ranked
  model table with attribute columns.
- **Media / model sentiment** ("how's the new Claude model") → aspects (coding, writing, speed,
  cost); weight X + Reddit + HN/web; output = *aspect × sentiment* with **consensus vs
  contention** + an overall verdict.
- **Company / event** ("SpaceX IPO thoughts") → bull case / bear case / key facts / sentiment
  trend; weight X + web + Reddit; output = balanced brief.

Behavior:
- Query **already states criteria** → echo the inferred rubric, proceed (still correctable).
- Query **under-specified** → propose a concrete rubric and get one quick confirm/adjust before
  spending the fan-out.
- Query fits **no template** → synthesize a rubric from scratch and confirm.
This is distinct from the **dev-time eval rubric** (§10) that grades Vox's *own* output.

## 8. Output format

A fixed, reused skeleton; the *dimensions* swap by query family (§7), the *shape* is constant:
1. **Methodology preamble** — the sources used and how each metric was derived.
2. **Ranked table** — columns map **one-to-one** to the rubric dimensions, ordered by the user's
   priority; cells annotated with corroborating-source signals and confidence marks.
3. **"How to read it"** — prose grouping picks by which dimension each one wins.
4. **Flags / excluded** — violations itemized with the **exact failing value** (never silently
   dropped, so the user can override).
5. **One honest single recommendation** — conditional framing allowed ("if X then A; if Z then B"),
   never a forced winner.
6. **2–3 concrete next actions.**
Plus, on demand, a **scoreboard/funnel**: per-source tally → deduped distinct total → surfaced →
evaluated → fit → excluded (with reasons), so search breadth is auditable.

**Confidence is per-figure**, not global: `✅ verified` · `~`/`*` estimate (with a basis
footnote) · `⚠️` caution · `❌` excluded. Single-source numbers and small samples are flagged
as such (e.g. "4.9/207 — high confidence on quality, lower on consistency").

## 9. Ranking & cross-source verification

**Routing table** (the core of the design):

| Sub-question | Primary source(s), v1 |
|---|---|
| Objective "goodness" | Web aggregators/critics + review-volume signals (+ Maps in P2) |
| Sentiment / anecdotal | `bird` (X) + `reddit-cli` + web critics |
| Precise facts | directed `WebFetch` reads (2+ corroborating sources) |
| Logistics / geo | Phase 2 (Maps) |

**Rules:**
- **Corroboration is the promotion gate:** a finalist must appear in **2+ channels**, and each
  pick is **labeled with which sources back it**; single-source picks are flagged.
- **Goodness = rating × volume**, not raw stars; reconcile incomparable scales rather than averaging.
- **Two-tier verification:** cheap triage signal → verified read for finalists; disclose which.
- **De-duplicate strictly** (by address for places; by exact model/entity otherwise) — resolve
  same-name / wrong-region collisions before comparing.
- **Resolve conflicts by recency and listing-type**; prefer two agreeing current sources over one
  old one; **never average or invent**.
- **Don't smooth away polarization** — a high average with a fat 1-star tail is real signal.
- **Treat user-provided data as ground-truth anchors** and re-measure with the same pipeline.

## 10. Rigor — the eval harness

Prompts aren't pytest-able, so rigor is an **evaluation loop**, not unit tests:
- **Golden queries** (~5–8) spanning the families, including a deliberately **sparse** topic to
  prove Vox says "thin evidence" instead of fabricating.
- **An LLM-judge rubric derived from the recipe**, graded per run: correct routing? every claim
  cited? **2-source corroboration gate** respected? blocked/failed sources listed? **no
  fabrication**? template followed? honest degradation on gaps? (Same adversarial-judge pattern
  that caught real bugs in `tiktok-cli`.)
- **Live capability smokes** — tiny checks that `reddit-cli`/`bird` actually return data.
- **The loop:** run goldens → judge → fix orchestrator/playbooks → repeat until the rubric passes
  clean. This is the "loop until rigorous" the project asked for.

## 11. Anti-bot ladder & posture

`vox-web` encodes the recipe's blocking map and **never retries a 403/429 — it pivots**:
1. URL variant (trailing slash, alternate domain).
2. Source pivot (Yelp→Tripadvisor/Restaurantji/Guru; official→aggregator; etc.).
3. **`WebSearch` titles/snippets** as data (surface prices/ratings even when the page 403s).
4. **Jina rung** — `https://r.jina.ai/<url>` returns the page as clean plaintext, past most
   403/JS-shells. **Opt-in and flagged**, because the request routes through a **third party**
   (Jina sees the fetch) and free-tier reliability varies.
5. If all fail, **report the gap** with a "sources that failed" list — never fabricate.

**Posture:** read-only, cite everything, polite degradation. Harder/aggressive bypass is out of
v1 scope and would be a separate, explicit decision.

## 12. Scope & phases

- **v1:** orchestrator + `vox-reddit` + `vox-x` + `vox-web` (Brave + Jina rung); rubric system;
  output template + confidence + scoreboard; corroboration gate; eval harness; `install.sh`.
- **Phase 2 — browser tier:** `vox-google` + `vox-maps` (Claude-in-Chrome, **orchestrator-driven,
  serialized**, runs concurrently with the stateless fan-out; degrades to web when the browser
  isn't paired).
- **Later:** TikTok / Instagram (capability-spike first — validate the CLI surface and whether
  they return *text* before trusting); the `vox "..."` shell wrapper over `csd`; video
  download + transcription.

## 13. Provenance & honesty notes

- The design is mined from prior sessions (Opus pass, 187 findings; `docs/vox-recipe.md`).
- The mining found **dense, corroborating** evidence for Reddit, X, Web, and Maps — and **zero**
  for TikTok/Instagram as sentiment sources, which is *why* they are deferred and gated.
- The single most load-bearing principle across all findings: **route by resource exclusivity,
  verify every fact across 2+ dated sources, never retry a block, and never fabricate — when
  data is missing, say so and show the blocked-source list.**
