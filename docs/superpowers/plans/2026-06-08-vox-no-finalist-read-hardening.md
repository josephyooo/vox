# Vox No-Finalist Read Hardening — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Give vox a second output skeleton for no-rankable-finalist (sentiment/news/reception) reads, make cross-source conflicts a first-class path (record → recheck-once → disclose honestly), and tighten the step-7 citation gate to check provenance, not just link adjacency.

**Architecture:** Pure prose-skill change in the `vox` repo. The orchestrator skill (`skills/vox/SKILL.md`) and its three references (`output-template.md`, `digest-contract.md`, `rubric-templates.md`) are edited; behavior is locked by concept-word contract tests (new `tests/test_no_finalist_read.py`, matching the `test_video_agy.py` style) plus eval goldens. No Python runtime code, no new tools, no new agents — every new rule is an orchestrator self-check.

**Tech Stack:** Markdown skill prose; pytest contract tests keyed on stable concept words; markdown eval goldens validated by `tests/test_goldens.py`. Gate: `.venv/bin/python -m pytest`, `.venv/bin/python -m ruff check tools tests eval`, `.venv/bin/python tools/validate_skills.py skills` (must print `[ok]` for every skill).

**Spec:** `docs/superpowers/specs/2026-06-08-vox-no-finalist-read-hardening-design.md`

---

## File Structure

| File | Responsibility | Task |
|---|---|---|
| `tests/test_no_finalist_read.py` (new) | Concept-word contract guard for the whole change | grows across Tasks 1–6 |
| `skills/vox/references/output-template.md` | Two skeletons (A ranked / B no-finalist) + confidence legend with the two carry-forward rules | Task 1 |
| `skills/vox/references/digest-contract.md` | New "Conflicts / disagreements across fetches" digest slot | Task 2 |
| `skills/vox/references/rubric-templates.md` | Each family names its skeleton; Behavior records the choice | Task 3 |
| `skills/vox/SKILL.md` | Step 1.5 records the skeleton; step 5 conflict-trigger + no-finalist branch; step 7 four honesty rules | Tasks 4–5 |
| `eval/goldens/claude-model-sentiment.md` | Updated to expect Skeleton B | Task 6 |
| `eval/goldens/event-conflict-sentiment.md` (new) | Exercises the conflict resolve-or-disclose path | Task 6 |

**Convention notes for the implementer (read before starting):**
- Contract tests key on **stable concept words**, lowercased, not exact sentences — see `tests/test_video_agy.py` and `tests/test_routing.py` for the exact idiom.
- The test module reads files fresh on each `pytest` run; constants defined at module top are fine even before the prose is edited (the files already exist).
- `validate_skills.py` only fails on broken `SKILL.md` local links. This change adds **no new links**, so it stays `[ok]`.
- Run every command from the repo root `/Users/joseph/projects/vox`.
- Each task commits the test + prose together so the gate is green at every commit.

---

## Task 1: Two output skeletons (A ranked / B no-finalist) + legend rules

**Files:**
- Create: `tests/test_no_finalist_read.py`
- Modify (full rewrite): `skills/vox/references/output-template.md`

- [ ] **Step 1: Write the failing test** — create `tests/test_no_finalist_read.py` with the module header + Task-1 assertions:

```python
# tests/test_no_finalist_read.py
"""Contract guard on the vox no-finalist read path.

Keyed on stable concept words (not exact sentences) so reasonable rewording survives,
but a silent DROP of Skeleton B, the conflict path, or any step-7 honesty rule fails the gate.
"""
from pathlib import Path

VOX = Path(__file__).resolve().parents[1] / "skills" / "vox"
GOLDENS = Path(__file__).resolve().parents[1] / "eval" / "goldens"

# Whole-skill concatenation, lowercased (cross-file concept presence).
TEXT = "\n".join(p.read_text() for p in sorted(VOX.rglob("*.md"))).lower()
# Per-file views (lowercased) for targeted assertions.
OUT = (VOX / "references" / "output-template.md").read_text().lower()
DIGEST = (VOX / "references" / "digest-contract.md").read_text().lower()
RUBRIC = (VOX / "references" / "rubric-templates.md").read_text().lower()
SKILL = (VOX / "SKILL.md").read_text().lower()


def test_two_named_skeletons_exist():
    assert "skeleton a" in TEXT
    assert "skeleton b" in TEXT
    assert "no rankable finalist" in TEXT


def test_skeleton_b_body_sections():
    assert "core facts" in OUT
    assert "| sources" in OUT  # the `Sources` column header in the claim table
    assert "sentiment & consensus" in OUT
    assert "themes & dissent" in OUT


def test_warn_mark_covers_conflicting_unverified():
    # ⚠️ no longer means only closure/budget risk
    assert "conflicting" in OUT or "unverified" in OUT


def test_legend_carry_forward_rules():
    assert "no silent confidence upgrade" in OUT
    assert "per-claim sources" in OUT
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `.venv/bin/python -m pytest tests/test_no_finalist_read.py -v`
Expected: FAIL — `test_two_named_skeletons_exist` and the others assert strings not yet in `output-template.md` (current file has a single skeleton, no "skeleton b").

- [ ] **Step 3: Rewrite `skills/vox/references/output-template.md`** with this exact content:

```markdown
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
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `.venv/bin/python -m pytest tests/test_no_finalist_read.py -v`
Expected: PASS (4 tests).

- [ ] **Step 5: Run the full gate**

Run: `.venv/bin/python -m pytest && .venv/bin/python -m ruff check tools tests eval && .venv/bin/python tools/validate_skills.py skills`
Expected: all tests pass, ruff "All checks passed!", validator prints `[ok]` for every skill.

- [ ] **Step 6: Commit**

```bash
git add tests/test_no_finalist_read.py skills/vox/references/output-template.md
git commit -m "feat(vox): two output skeletons (A ranked / B no-finalist) + legend carry-forward rules

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Task 2: Digest "Conflicts / disagreements" slot

**Files:**
- Modify: `skills/vox/references/digest-contract.md`
- Modify: `tests/test_no_finalist_read.py` (append one test)

- [ ] **Step 1: Write the failing test** — append to `tests/test_no_finalist_read.py`:

```python
def test_digest_has_conflicts_slot():
    assert "conflicts / disagreements across fetches" in DIGEST
    assert "likely extraction error" in DIGEST
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `.venv/bin/python -m pytest tests/test_no_finalist_read.py::test_digest_has_conflicts_slot -v`
Expected: FAIL — the phrase is not yet in `digest-contract.md`.

- [ ] **Step 3: Edit `skills/vox/references/digest-contract.md`.** Replace the current sections 4–7 block:

```markdown
4. **Corroboration notes** — what else (in this source) supports each claim; recurrence counts.
5. **Estimates labeled** — bullet list of every `~`/estimate value and the basis for it.
6. **Sources that failed (not used)** — URL + reason (403 / 429 / JS-shell / not-listed /
   wrong-entity). Empty is fine, but state "none".
7. **Bottom line** — a 1–3 sentence TL;DR for the orchestrator.
```

with (inserts the new section 5, renumbers the rest):

```markdown
4. **Corroboration notes** — what else (in this source) supports each claim; recurrence counts.
5. **Conflicts / disagreements across fetches** — anywhere two fetches disagree on a value/date/
   figure, or a value looks like a likely extraction error. Record: the claim, value A (URL),
   value B (URL), and which (if either) you believe + why. Empty is fine — state "none".
6. **Estimates labeled** — bullet list of every `~`/estimate value and the basis for it.
7. **Sources that failed (not used)** — URL + reason (403 / 429 / JS-shell / not-listed /
   wrong-entity). Empty is fine, but state "none".
8. **Bottom line** — a 1–3 sentence TL;DR for the orchestrator.
```

Then update the **Status** line at the bottom of the same file from:

```markdown
If the source yielded nothing, return sections 1, 6, 7 with **Status: no-signal** and say so
plainly. Do not invent items to fill the table.
```

to (the failed + bottom-line sections renumbered 7 and 8):

```markdown
If the source yielded nothing, return sections 1, 7, 8 with **Status: no-signal** and say so
plainly. Do not invent items to fill the table.
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `.venv/bin/python -m pytest tests/test_no_finalist_read.py::test_digest_has_conflicts_slot -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add tests/test_no_finalist_read.py skills/vox/references/digest-contract.md
git commit -m "feat(vox): digest gains a Conflicts/disagreements-across-fetches slot

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Task 3: Wire each rubric family to its skeleton

**Files:**
- Modify: `skills/vox/references/rubric-templates.md`
- Modify: `tests/test_no_finalist_read.py` (append one test)

- [ ] **Step 1: Write the failing test** — append to `tests/test_no_finalist_read.py`:

```python
def test_rubric_families_name_skeletons():
    assert "skeleton a" in RUBRIC
    assert "skeleton b" in RUBRIC
    assert "record the chosen skeleton" in RUBRIC
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `.venv/bin/python -m pytest tests/test_no_finalist_read.py::test_rubric_families_name_skeletons -v`
Expected: FAIL — `rubric-templates.md` does not yet mention skeletons.

- [ ] **Step 3: Edit `skills/vox/references/rubric-templates.md`** — make these four output-line replacements and add one Behavior bullet.

Replace `- Output: ranked venue table.` with:
```markdown
- Output: Skeleton A — ranked venue table.
```

Replace `- Output: ranked model table with attribute columns.` with:
```markdown
- Output: Skeleton A — ranked model table with attribute columns.
```

Replace `- Output: aspect × sentiment with CONSENSUS vs CONTENTION + an overall verdict.` with:
```markdown
- Output: Skeleton B — aspect × sentiment with CONSENSUS vs CONTENTION + an overall verdict.
```

Replace `- Output: balanced brief.` with:
```markdown
- Output: Skeleton B (balanced brief — core facts + sentiment & consensus + themes & dissent).
```

In the `## Behavior` block, after the existing three bullets, add:
```markdown
- Record the chosen skeleton (A/B) as part of the confirmed rubric — by the universal rule: rankable
  finalists → A, else → B (a synthesized-from-scratch rubric or a no-named-family query like breaking
  news still picks one). Render (step 7) uses it rather than re-deciding the shape.
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `.venv/bin/python -m pytest tests/test_no_finalist_read.py::test_rubric_families_name_skeletons -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add tests/test_no_finalist_read.py skills/vox/references/rubric-templates.md
git commit -m "feat(vox): rubric families name their output skeleton (A/B)

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Task 4: SKILL.md — step 1.5 records skeleton; step 5 conflict-trigger + no-finalist branch

**Files:**
- Modify: `skills/vox/SKILL.md`
- Modify: `tests/test_no_finalist_read.py` (append two tests)

- [ ] **Step 1: Write the failing test** — append to `tests/test_no_finalist_read.py`:

```python
def test_step15_records_skeleton():
    assert "record the output skeleton" in SKILL


def test_step5_conflict_trigger_and_no_finalist_branch():
    assert "conflict trigger" in SKILL
    assert "no-finalist branch" in SKILL
    assert "does not clear" in SKILL          # 2+ promotes but does NOT clear a conflict
    assert "sources disagree" in SKILL        # the disclose-don't-pick render
    assert "intentionally skipped" in SKILL   # the no-finalist Wave-2 decision is stated
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `.venv/bin/python -m pytest tests/test_no_finalist_read.py -k "step15 or step5" -v`
Expected: FAIL — these phrases are not yet in `SKILL.md`.

- [ ] **Step 3: Edit `skills/vox/SKILL.md`.** First replace the step 1.5 block:

```markdown
   1.5 **Propose the rubric & confirm** (dimensions + source plan + "good" bar) per
   `references/rubric-templates.md`, UNLESS the query already states criteria (then echo + proceed;
   skip the confirm if the user said "just run it").
```

with:

```markdown
   1.5 **Propose the rubric & confirm** (dimensions + source plan + "good" bar) per
   `references/rubric-templates.md`, UNLESS the query already states criteria (then echo + proceed;
   skip the confirm if the user said "just run it"). **Record the output skeleton** (A = rankable
   finalists; B = no rankable finalist) as part of the confirmed rubric, by the rule rankable→A /
   else→B; carry it to render (step 7).
```

Then replace the step 5 block:

```markdown
5. **Wave 2 — verify.** For each finalist, dispatch a narrow stateless verifier to pin facts +
   recent sentiment (two-tier: cheap triage → verified read; disclose which).
```

with:

```markdown
5. **Wave 2 — verify (finalist OR contested claim).**
   - **Per-finalist (Skeleton A):** for each finalist, dispatch a narrow stateless verifier to pin
     facts + recent sentiment (two-tier: cheap triage → verified read; disclose which).
   - **Conflict trigger (BOTH skeletons, MANDATORY):** if any digest's "Conflicts / disagreements"
     slot is non-empty, or a high-stakes claim (event date, toll, who/what/where) is contested or
     self-flagged a likely extraction error, you MUST resolve it before render — EVEN IF the headline
     facts already corroborate 2+ channels. The 2+-channel rule PROMOTES a candidate; it does NOT
     clear a conflicting figure. Resolve cheaply: ONE narrow re-fetch of just that fact (your own
     WebFetch/WebSearch; escalate to a directed `vox-web` verifier only if the re-fetch is itself
     blocked — never retry a 403/429).
   - **No-finalist branch (Skeleton B):** there is no per-finalist wave — instead run a lightweight
     corroboration pass: every load-bearing claim/number is in 2+ channels OR carries a single-source
     hedge, and each contested fact gets the one narrow re-fetch above. State in your reasoning that
     the per-finalist wave was intentionally skipped and why.
   - **Unresolved → disclose, don't pick:** if the re-fetch can't resolve it, render BOTH values with
     `⚠️ (sources disagree: X vs Y — unverified)`. Never silently choose one; the phrase "corroborated
     on every key fact" is FORBIDDEN while any conflict is open.
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `.venv/bin/python -m pytest tests/test_no_finalist_read.py -k "step15 or step5" -v`
Expected: PASS (2 tests).

- [ ] **Step 5: Run the full gate** (SKILL.md changed → validate_skills must stay `[ok]`)

Run: `.venv/bin/python -m pytest && .venv/bin/python -m ruff check tools tests eval && .venv/bin/python tools/validate_skills.py skills`
Expected: all pass; validator `[ok]` for every skill (no new links added).

- [ ] **Step 6: Commit**

```bash
git add tests/test_no_finalist_read.py skills/vox/SKILL.md
git commit -m "feat(vox): step 5 conflict-trigger + no-finalist verify branch; step 1.5 records skeleton

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Task 5: SKILL.md — step 7 four honesty rules (provenance, not just adjacency)

**Files:**
- Modify: `skills/vox/SKILL.md`
- Modify: `tests/test_no_finalist_read.py` (append one test)

- [ ] **Step 1: Write the failing test** — append to `tests/test_no_finalist_read.py`:

```python
def test_step7_four_honesty_rules():
    assert "no silent confidence upgrade" in SKILL
    assert "per-claim sources" in SKILL
    assert "quote provenance" in SKILL
    assert "paraphrase via" in SKILL
    assert "links all n" in SKILL  # "Corroboration count links all N"
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `.venv/bin/python -m pytest tests/test_no_finalist_read.py::test_step7_four_honesty_rules -v`
Expected: FAIL — step 7 currently has only the citation-completeness gate.

- [ ] **Step 3: Edit `skills/vox/SKILL.md`.** Find the end of the existing step-7 citation-completeness gate (the line ending `…present it as an unattributed paraphrase.`). Immediately after that line, and before line `8. **Follow-ups = live RE-WEIGHTING**…`, insert this block (keep the existing citation gate intact):

```markdown
   **Honesty gate (before emitting — provenance, not just adjacency; run as self-checks, no new
   agents):**
   1. **No silent confidence upgrade** — a fact any contributing digest marked `⚠️` / `SINGLE-SOURCE`
      / conflicting MUST keep at least that caution; you may LOWER confidence with justification but
      NEVER raise it above what the digest reported.
   2. **Per-claim sources** — tag each promoted fact with its real corroborating sources / channel
      count (`web-only`, `web+Reddit`); a blanket "all 2+ corroborated" is forbidden when any claim is
      1-channel.
   3. **Quote provenance** — a quote attributed to a NAMED person/outlet must link the page where it
      was actually READ. If recovered via an aggregator that re-quotes, strip the quotation marks and
      tag `[paraphrase via <aggregator>]`, or drop it — never render an aggregator re-quote as a
      verbatim attribution to the original.
   4. **Corroboration count links all N** — any count/strength claim ("N outlets", "genuine
      consensus") must inline-link EVERY counted source, or downgrade to a non-numeric hedge
      ("multiple critics"); a snippet-only / 403'd source may NOT be tallied into N.
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `.venv/bin/python -m pytest tests/test_no_finalist_read.py::test_step7_four_honesty_rules -v`
Expected: PASS.

- [ ] **Step 5: Run the full gate**

Run: `.venv/bin/python -m pytest && .venv/bin/python -m ruff check tools tests eval && .venv/bin/python tools/validate_skills.py skills`
Expected: all pass; validator `[ok]` for every skill.

- [ ] **Step 6: Commit**

```bash
git add tests/test_no_finalist_read.py skills/vox/SKILL.md
git commit -m "feat(vox): step 7 honesty gate — quote provenance, corroboration-count, no silent upgrade

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Task 6: Eval goldens — update sentiment golden + add conflict golden

**Files:**
- Modify: `eval/goldens/claude-model-sentiment.md`
- Create: `eval/goldens/event-conflict-sentiment.md`
- Modify: `tests/test_no_finalist_read.py` (append two tests)

- [ ] **Step 1: Write the failing test** — append to `tests/test_no_finalist_read.py`:

```python
def test_sentiment_golden_updated_to_skeleton_b():
    low = (GOLDENS / "claude-model-sentiment.md").read_text().lower()
    assert "skeleton b" in low


def test_conflict_golden_exists_and_exercises_disclosure():
    g = GOLDENS / "event-conflict-sentiment.md"
    assert g.exists()
    low = g.read_text().lower()
    assert "skeleton b" in low
    assert "conflicts / disagreements" in low
    assert "sources disagree" in low
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `.venv/bin/python -m pytest tests/test_no_finalist_read.py -k "golden" -v`
Expected: FAIL — `claude-model-sentiment.md` has no "skeleton b" yet, and `event-conflict-sentiment.md` does not exist.

- [ ] **Step 3a: Rewrite `eval/goldens/claude-model-sentiment.md`** with this exact content:

```markdown
## Query
how good is the new Claude model for coding

## Family
media / model sentiment (no rankable finalist → Skeleton B)

## Expectations
- Routes to X + Reddit + HN/web.
- Renders Skeleton B (no rankable finalist): Core facts (`Core fact | Finding | Confidence | Sources`)
  + Sentiment & consensus (aspect × sentiment — coding, speed, cost — with CONSENSUS vs CONTENTION)
  + Themes & dissent (the minority view kept, not flattened), and a Bottom line that is one honest
  synthesis — NOT a forced winner.
- Per-claim Sources tagged; no silent confidence upgrade above what a digest reported.
- Dated quotes with permalinks linking the page actually read; an "N outlets/sources" count links all
  N; no fabricated benchmarks. Canonical "Sources that failed / blocked" line present.
```

- [ ] **Step 3b: Create `eval/goldens/event-conflict-sentiment.md`** with this exact content:

```markdown
## Query
what happened in the recent MARTA train stabbing in Atlanta and how are people reacting

## Family
company / event (no rankable finalist → Skeleton B)

## Expectations
- Renders Skeleton B: Core facts table (`Core fact | Finding | Confidence | Sources`) covering
  what / when / where / current status, then Sentiment & consensus, then Themes & dissent.
- A cross-source date/figure conflict (one fetch's date or count disagrees with another, or a value is
  a likely extraction error) is recorded in the source digests' "Conflicts / disagreements" slot and
  MUST NOT ship unverified: it is either RESOLVED by one narrow re-fetch, or DISCLOSED with
  `⚠️ (sources disagree: X vs Y — unverified)` — never silently picked, and never "corroborated on
  every key fact" while a conflict is open.
- The per-finalist Wave-2 wave is intentionally skipped (no rankable finalist) and that is stated.
- Per-claim Sources tagged; a 1-channel claim is not hidden inside a blanket "2+"; no silent
  confidence upgrade.
- Every quote links the page actually read (no aggregator re-quote rendered as verbatim attribution);
  an "N outlets" count links all N. Canonical "Sources that failed / blocked" line present.
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `.venv/bin/python -m pytest tests/test_no_finalist_read.py -k "golden" -v`
Expected: PASS (2 tests). Note `tests/test_goldens.py` auto-validates the new golden's `## Query / ## Family / ## Expectations` structure.

- [ ] **Step 5: Run the full gate**

Run: `.venv/bin/python -m pytest && .venv/bin/python -m ruff check tools tests eval && .venv/bin/python tools/validate_skills.py skills`
Expected: all pass (including `test_goldens.py`), ruff clean, validator `[ok]` for every skill.

- [ ] **Step 6: Commit**

```bash
git add tests/test_no_finalist_read.py eval/goldens/claude-model-sentiment.md eval/goldens/event-conflict-sentiment.md
git commit -m "test(vox): goldens for Skeleton B sentiment read + conflict resolve-or-disclose

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Final verification

- [ ] **Run the complete gate one more time from repo root:**

Run: `.venv/bin/python -m pytest && .venv/bin/python -m ruff check tools tests eval && .venv/bin/python tools/validate_skills.py skills`
Expected: pytest all green (including the 11 new assertions in `test_no_finalist_read.py` and `test_goldens.py`), ruff "All checks passed!", validator `[ok]` for every skill.

- [ ] **Sanity-read the rendered prose:** open `skills/vox/references/output-template.md` and confirm Skeleton A and Skeleton B both read cleanly and the shared invariants are not duplicated; open `skills/vox/SKILL.md` and confirm step 5 and step 7 read as coherent additions, not duplications.

---

## Notes for the implementer

- **DRY:** the shared invariants live once at the top of `output-template.md`; Skeletons A and B reference them, they are not re-listed in full.
- **YAGNI:** do NOT add new rubric families (breaking-news, just-released-media) or any Tier-4 polish — they are explicitly out of scope per the spec.
- **No behavior code:** every new rule is an orchestrator self-check in prose. There is no Python to write beyond the contract tests.
- **Concept-word tests are intentionally loose:** if you reword the prose, keep the asserted concept words (e.g. "skeleton b", "no silent confidence upgrade", "sources disagree", "paraphrase via", "conflicts / disagreements across fetches") so the gate still binds.
