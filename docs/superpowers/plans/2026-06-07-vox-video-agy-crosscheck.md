# vox-video `agy` Entity Cross-Check Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add `agy` (Gemini) as a supplementary, soft-gated entity-layer cross-check to the `vox-video` skill — correcting garbled proper nouns and surfacing missed on-screen entities — without ever displacing the `mw + ffmpeg + vision` stack as source-of-record.

**Architecture:** `vox-video` is a PROSE skill (no Python). The deliverable is one new focused reference (`agy-crosscheck.md`) holding the full contract (prompt, model, three robustness guards, `agy.md` artifact shape, reconciliation rules R-A1..R-A5), wired into the existing `SKILL.md` + `ingest-playbook.md` + `digest-extension.md`, guarded by a deterministic contract test and an eval-golden expectation. Single repo: `/Users/joseph/projects/vox`.

**Tech Stack:** Markdown skill prose; Python `pytest` contract tests; `ruff`; `tools/validate_skills.py` (checks frontmatter + that every SKILL.md local link resolves).

---

## Context the engineer needs

- **Repo root:** `/Users/joseph/projects/vox`. Run all commands from there.
- **The gate (must stay green after every task):**
  - `.venv/bin/python -m pytest` → expect `N passed`
  - `.venv/bin/python -m ruff check tools tests eval` → expect `All checks passed!`
  - `.venv/bin/python tools/validate_skills.py skills` → expect a `[ok]` line for **every** skill (no `[FAIL]`); exit 0
- **Validator gotcha (ordering-critical):** `tools/validate_skills.py` fails any SKILL.md local link whose target file does not exist. Therefore `references/agy-crosscheck.md` MUST be created (Task 1) **before** `SKILL.md` links to it (Task 2). Do the tasks in order.
- **Design spec (source of truth):** `docs/superpowers/specs/2026-06-07-vox-video-agy-crosscheck-design.md`.
- **Existing skill files you will touch:**
  - `skills/vox-video/SKILL.md`
  - `skills/vox-video/references/ingest-playbook.md`
  - `skills/vox-video/references/digest-extension.md`
- **Existing test style to mirror:** `tests/test_routing.py` (reads skill prose, asserts stable concept words).
- **ruff config:** line-length 100, target py310. Keep every new `.py` line ≤ 100 chars, no unused imports.

---

## File Structure

| File | New/Mod | Responsibility |
|------|---------|----------------|
| `skills/vox-video/references/agy-crosscheck.md` | **New** | The single canonical contract: what agy is/isn't, soft gating, the call (prompt+model), the three guards, `agy.md` shape, reconciliation rules R-A1..R-A5. |
| `tests/test_video_agy.py` | **New** | Deterministic contract guard over the vox-video prose (concept words). |
| `skills/vox-video/SKILL.md` | Mod | Bootstrap soft-probe; Phase-1 agy step; Phase-2 reconciliation pointer + link to the new reference. |
| `skills/vox-video/references/ingest-playbook.md` | Mod | The agy ingest stage in the workdir layout + per-video steps + `status.json` field. |
| `skills/vox-video/references/digest-extension.md` | Mod | Output/digest notes for agy (sources-that-failed, transparent correction label) + pointer to R-A rules. |
| `eval/goldens/video-collection.md` | Mod | agy expectation lines under `## Expectations`. |

---

## Task 1: Contract test + the `agy-crosscheck.md` reference

**Files:**
- Test: `tests/test_video_agy.py` (create)
- Create: `skills/vox-video/references/agy-crosscheck.md`

- [ ] **Step 1: Write the failing test**

Create `tests/test_video_agy.py` with exactly this content:

```python
# tests/test_video_agy.py
"""Contract guard on the vox-video agy entity cross-check.

Keyed on stable concept words (not exact sentences) so reasonable rewording survives,
but a silent DROP of any agy guardrail fails the gate.
"""
from pathlib import Path

VIDEO = Path(__file__).resolve().parents[1] / "skills" / "vox-video"
# Concatenate all prose in the vox-video skill (SKILL.md + references/*.md), lowercased.
TEXT = "\n".join(p.read_text() for p in sorted(VIDEO.rglob("*.md"))).lower()


def test_agy_crosscheck_reference_exists():
    assert (VIDEO / "references" / "agy-crosscheck.md").exists()


def test_agy_is_supplementary_entity_layer_crosscheck():
    assert "agy" in TEXT
    assert "cross-check" in TEXT
    assert "entity" in TEXT
    assert "supplementary" in TEXT
    # the mw+vision stack stays the source of record
    assert "source-of-record" in TEXT


def test_no_phantom_quotes_still_binds():
    # R-A3: agy never creates a spoken-claim quote
    assert "phantom" in TEXT
    assert "spoken" in TEXT


def test_agy_unavailable_is_non_halting():
    assert "unavailable" in TEXT
    assert "never a halt" in TEXT


def test_three_robustness_guards_documented():
    # 1) hard external timeout  2) success-by-output-not-exit-code  3) retry-once
    assert "timeout" in TEXT
    assert "exit code" in TEXT
    assert "retry" in TEXT
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `.venv/bin/python -m pytest tests/test_video_agy.py -v`
Expected: FAIL — `test_agy_crosscheck_reference_exists` fails (file missing) and the concept-word tests fail (words absent from current prose).

- [ ] **Step 3: Create the `agy-crosscheck.md` reference**

Create `skills/vox-video/references/agy-crosscheck.md` with exactly this content:

```markdown
# agy entity cross-check (supplementary)

`agy` (Gemini via the user's edu subscription) is a **supplementary** entity-layer cross-check layered
on the disciplined `mw + ffmpeg + vision` stack. It does TWO jobs only: (1) **correct garbled proper
nouns** in entity names — mw's weak spot (mw "store wrecks" / "Elisa's" / "Theo's habitashery" → agy
"store recs" / "Illisa's" / "Theo's Haberdashery"); (2) **surface on-screen entities** the 5-frame
%-sample missed (agy reads the WHOLE video). It is NOT a source of spoken quotes, timestamps/frame
anchors, sentiment, or comments — the stack stays **source-of-record** for all of those. agy is
supplementary, never a replacement.

## Soft gating (NOT a hard prereq)
Unlike `mw` / `ffmpeg` / `tiktok-cli` (hard prereqs that HALT when missing), `agy` is SOFT-probed at
bootstrap with `agy --help`:
- present → cross-check **ENABLED**.
- absent → cross-check **DISABLED**, recorded as a coverage note ("agy entity cross-check unavailable —
  names are mw/vision-only"); the pipeline PROCEEDS normally. This is **never a halt** — the contrast
  with the hard prereqs.

## The call (Phase-1 ingest, video-only, before media cleanup)
Run ONCE per downloaded video mp4, **before `video.mp4` is removed** (agy needs the file present). Photo
carousels SKIP agy (record `agy: skipped`) — they keep their vision-on-slides path.

Model `Gemini 3.1 Pro (Low)` (passed explicitly; agy's own default is Gemini 3.5 Flash Medium). Fixed
deterministic prompt → three parseable sections:

    agy -p "Analyze the video file <id>.mp4 in this workspace. Produce EXACTLY three sections:
    ## spoken — verbatim speech only; if there is no speech write exactly: (no speech)
    ## on-screen — any text visible on screen; if none write: (none)
    ## entities — bullet list of every business/place/brand name, each tagged (spoken) or (on-screen); if none write: (none)
    Do not invent or infer anything not present in the file." \
      --model "Gemini 3.1 Pro (Low)" --add-dir <workdir> --dangerously-skip-permissions

Write the result to `<workdir>/<id>/agy.md`.

## The three mandatory guards (each earned from live validation)
1. **Hard external timeout (~150s per call).** agy can HANG past its own `--print-timeout` on malformed
   media (a 70s-video / 15s-audio desync hung ~42 min). Bound every call and kill on overrun. (Real
   videos returned well under 150s.)
2. **Success judged by OUTPUT, not exit code.** agy returned exit 0 with `Error: timed out waiting for
   response` as its body. A run is a FAILURE if its output is empty, is missing the `##` section
   markers, or contains `Error: timed out`.
3. **Retry once on flake.** ~1/3 of clean-input runs flaked (timeout error). On a failed output-check,
   retry exactly once, then give up.

On give-up: write `agy: unavailable (<reason>)` and CONTINUE — never abort the video or the collection.

## agy.md artifact shape
    # agy cross-check — <id>
    status: ok            # or: unavailable (<reason>) | skipped (photo) | disabled (agy absent)
    ## spoken
    <verbatim, or (no speech)>
    ## on-screen
    <text, or (none)>
    ## entities
    - <name> (spoken|on-screen)

`status.json` gains an `agy` field: `ok | unavailable | skipped | disabled`. Re-runs skip resolved items.

## Reconciliation rules (Phase-2 extraction; consume agy.md at the ENTITY layer only)
These layer onto the five honesty rules in [digest-extension](digest-extension.md) and NEVER override them.

- **R-A1 — Spelling reconciliation, by precedence.** On a same-referent spelling disagreement (matched by
  token similarity), the canonical name follows: (1) an on-screen **NAME CARD** read by vision (storefront
  sign / Maps card — the business's own text, authoritative); (2) `agy`; (3) the `mw` transcript (weakest,
  mishears names). So agy overrides mw for SPOKEN-only entities but does NOT override a vision-read
  on-screen name card. The claim's quote text + timestamp/frame provenance stay exactly as the stack
  recorded them; log the correction transparently ("canonical name per agy cross-check; mw heard 'Elisa's'").
- **R-A2 — agy-only on-screen entities.** An on-screen entity agy caught but the frame-sample missed is
  ADDED as a claim sourced `agy on-screen (no frame anchor)`, at **lower confidence** than a frame-anchored
  on-screen claim; it must still corroborate downstream — never promoted on agy alone.
- **R-A3 — No phantom quotes via agy.** agy NEVER creates a spoken-claim quote. Honesty Rule 2 still
  binds: a spoken quote exists ONLY if the **stack's** transcript status is `ok`. agy touches entity
  **spelling** only; we never quote from agy's transcript.
- **R-A4 — agy never deletes.** agy misses don't remove stack claims; stack entities agy missed are kept.
  Disagreements resolve as R-A1 or R-A2, never a deletion.
- **R-A5 — Per-video unavailability is recorded.** `agy: unavailable` → extract stack-only for that video
  and note in the digest's "sources that failed" that the cross-check didn't run (a possibly-garbled name
  isn't silently trusted as verified).
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `.venv/bin/python -m pytest tests/test_video_agy.py -v`
Expected: PASS (all 5 tests). The new reference supplies every concept word.

- [ ] **Step 5: Run ruff + validator (sanity)**

Run: `.venv/bin/python -m ruff check tools tests eval`
Expected: `All checks passed!`
Run: `.venv/bin/python tools/validate_skills.py skills`
Expected: `[ok] vox-video` (and `[ok]` for every other skill). The new reference is not yet linked from SKILL.md, so the validator does not require it — but it must not regress any existing link.

- [ ] **Step 6: Commit**

```bash
git add tests/test_video_agy.py skills/vox-video/references/agy-crosscheck.md
git commit -m "$(cat <<'EOF'
feat(vox-video): agy entity cross-check reference + contract test

New references/agy-crosscheck.md holds the full contract (supplementary entity-layer
role, soft gating, the call/prompt/model, the three robustness guards, agy.md shape,
reconciliation rules R-A1..R-A5). tests/test_video_agy.py locks the guardrails.

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>
EOF
)"
```

---

## Task 2: Wire the cross-check into SKILL.md + ingest-playbook + digest-extension

**Files:**
- Modify: `skills/vox-video/SKILL.md`
- Modify: `skills/vox-video/references/ingest-playbook.md`
- Modify: `skills/vox-video/references/digest-extension.md`
- Test: `tests/test_video_agy.py` (add one assertion)

- [ ] **Step 1: Add the failing wiring assertion to the test**

Append this function to `tests/test_video_agy.py`:

```python
def test_skill_entrypoint_and_playbooks_wire_agy():
    skill = (VIDEO / "SKILL.md").read_text().lower()
    ingest = (VIDEO / "references" / "ingest-playbook.md").read_text().lower()
    # the skill entrypoint points at the cross-check and its reference
    assert "agy" in skill
    assert "agy-crosscheck" in skill
    # the ingest playbook documents the per-video agy stage + status field
    assert "agy" in ingest
    assert "agy.md" in ingest
```

- [ ] **Step 2: Run it to verify it fails**

Run: `.venv/bin/python -m pytest tests/test_video_agy.py::test_skill_entrypoint_and_playbooks_wire_agy -v`
Expected: FAIL — `SKILL.md` / `ingest-playbook.md` do not yet mention agy.

- [ ] **Step 3: Edit `SKILL.md` — bootstrap soft-probe**

In `skills/vox-video/SKILL.md`, find this block:

```markdown
If `mw`, `ffmpeg`, or `tiktok-cli` is missing → **HALT**: return Status `no-capability` naming the
missing tool + its one-line install, and do NOT degrade to a partial answer.
```

Insert immediately AFTER it:

```markdown

**Soft probe (supplementary, non-halting):** `agy --help` — enables the supplementary entity
cross-check ([agy-crosscheck](references/agy-crosscheck.md)). If `agy` is absent, the cross-check is
DISABLED and recorded as a coverage note; the pipeline PROCEEDS — this is **never a halt**, unlike the
hard prereqs above.
```

- [ ] **Step 4: Edit `SKILL.md` — Phase 1 step list**

Find this line:

```markdown
download → `mw` transcript → `ffmpeg` frames → vision on-screen text → comments, writing a cached
```

Replace it with:

```markdown
download → `mw` transcript → `ffmpeg` frames → vision on-screen text → `agy` entity cross-check
(video-only, supplementary; see [agy-crosscheck](references/agy-crosscheck.md)) → comments, writing a cached
```

- [ ] **Step 5: Edit `SKILL.md` — Phase 2 reconciliation pointer**

Find this block:

```markdown
with **comments as a separate crowd channel**. Apply the five honesty rules in
[digest-extension](references/digest-extension.md) — above all: **no spoken-claim quote unless that
video's transcript status is `ok`**. Dedupe mentions to canonical entities; count cross-video
corroboration (`mention_count` / distinct creators).
```

Replace it with:

```markdown
with **comments as a separate crowd channel**. Apply the five honesty rules in
[digest-extension](references/digest-extension.md) — above all: **no spoken-claim quote unless that
video's transcript status is `ok`**. Then **reconcile entities against the `agy` cross-check** (rules
R-A1..R-A5 in [agy-crosscheck](references/agy-crosscheck.md)): prefer the better-sourced spelling and add
agy-only on-screen entities at lower confidence — but `agy` **never** creates a spoken quote (Rule 2
still binds). Dedupe mentions to canonical entities; count cross-video corroboration (`mention_count` /
distinct creators).
```

- [ ] **Step 6: Edit `ingest-playbook.md` — workdir layout**

In `skills/vox-video/references/ingest-playbook.md`, find:

```markdown
    onscreen.md                 # Claude vision over frames (prices/addresses/on-screen text)
    status.json                 # {download,transcribe,frames,onscreen,comments}: ok|empty|skipped|error
```

Replace with:

```markdown
    onscreen.md                 # Claude vision over frames (prices/addresses/on-screen text)
    agy.md                      # agy cross-check (video-only, supplementary) — see agy-crosscheck.md
    status.json                 # {download,transcribe,frames,onscreen,agy,comments}: ok|empty|skipped|error|unavailable|disabled
```

- [ ] **Step 7: Edit `ingest-playbook.md` — per-video step**

Find this step:

```markdown
8. **Comments** — `tiktok-cli --json video comments "<url>" -n 50` → `comments.json`; best-effort.
   On rate-limit record `comments: none_fetched` (NOT neutral).
9. Write the item's `status.json`.
```

Replace with:

```markdown
8. **agy cross-check** (video-only, supplementary; SKIP for photo carousels → `agy: skipped`) — run
   `agy` ONCE on `video.mp4` **before it is removed** → `agy.md`, per
   [agy-crosscheck](agy-crosscheck.md). Best-effort with three mandatory guards: a hard ~150s external
   timeout (agy can hang past its own timeout), success judged by OUTPUT not exit code (it returns exit
   0 with `Error: timed out` as the body), and retry-once-on-flake. On give-up record `agy: unavailable`
   and continue — **never a halt**. If `agy` was absent at bootstrap, record `agy: disabled` and skip.
9. **Comments** — `tiktok-cli --json video comments "<url>" -n 50` → `comments.json`; best-effort.
   On rate-limit record `comments: none_fetched` (NOT neutral).
10. Write the item's `status.json`.
```

- [ ] **Step 8: Edit `digest-extension.md` — output notes + R-A pointer**

In `skills/vox-video/references/digest-extension.md`, find this line (end of the "How video signals map" list):

```markdown
- **Sources that failed** — list ingest failures explicitly: empty-transcript videos (by id),
  unresolved/garbled entities, rate-limited comments (`none_fetched` ≠ neutral), un-enumerated items.
```

Replace with:

```markdown
- **Sources that failed** — list ingest failures explicitly: empty-transcript videos (by id),
  unresolved/garbled entities, rate-limited comments (`none_fetched` ≠ neutral), un-enumerated items,
  and per-video `agy: unavailable` (the entity cross-check didn't run — a possibly-garbled name isn't
  silently trusted) plus global `agy: disabled` when agy is absent.
- **agy entity cross-check (supplementary)** — reconcile entity NAMES against `agy.md` per rules
  R-A1..R-A5 in [agy-crosscheck](agy-crosscheck.md): a corrected name carries a transparent
  "via agy cross-check" note; an agy-only on-screen entity carries a lower-confidence "no frame anchor"
  label; `agy` NEVER becomes the source of a spoken quote (Rule 2 below still binds).
```

- [ ] **Step 9: Run the full gate**

Run: `.venv/bin/python -m pytest`
Expected: `N passed` (includes the new `test_skill_entrypoint_and_playbooks_wire_agy`).
Run: `.venv/bin/python -m ruff check tools tests eval`
Expected: `All checks passed!`
Run: `.venv/bin/python tools/validate_skills.py skills`
Expected: `[ok] vox-video` and `[ok]` for every other skill (the new `agy-crosscheck.md` link from SKILL.md now resolves because Task 1 created the file).

- [ ] **Step 10: Commit**

```bash
git add skills/vox-video/SKILL.md skills/vox-video/references/ingest-playbook.md skills/vox-video/references/digest-extension.md tests/test_video_agy.py
git commit -m "$(cat <<'EOF'
feat(vox-video): wire agy cross-check into bootstrap, ingest, extract, digest

Soft non-halting agy --help probe; agy stage in the ingest playbook (video-only,
before media cleanup, three guards, status.json agy field); Phase-2 entity
reconciliation pointer; digest output notes (sources-that-failed + transparent
correction label). Contract test asserts the wiring is present.

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>
EOF
)"
```

---

## Task 3: Eval golden expectation lines

**Files:**
- Modify: `eval/goldens/video-collection.md`

- [ ] **Step 1: Add the agy expectations**

In `eval/goldens/video-collection.md`, find the final expectation bullet:

```markdown
- If `mw`/`ffmpeg`/`tiktok-cli` is missing: HALTS by default naming the missing prereq; never a
  partial answer.
```

Insert immediately AFTER it:

```markdown
- agy entity cross-check (supplementary, soft-gated): a proper-noun correction (a name `mw` garbled) is
  shown transparently as "via agy cross-check"; `agy` is NEVER the source of a spoken-claim quote
  (Rule 2 still binds); an agy-only on-screen entity is added at lower confidence with a "no frame
  anchor" label.
- If `agy` is unavailable for a video (flake/timeout) or absent (disabled), it is noted in "sources
  that failed / blocked" — NOT halted; the disciplined `mw`/`ffmpeg`/vision stack remains
  source-of-record.
```

- [ ] **Step 2: Run the golden + full gate**

Run: `.venv/bin/python -m pytest tests/test_goldens.py -v`
Expected: PASS (`video-collection.md` still has `## Query` / `## Family` / `## Expectations`).
Run: `.venv/bin/python -m pytest`
Expected: `N passed`.
Run: `.venv/bin/python -m ruff check tools tests eval` → `All checks passed!`
Run: `.venv/bin/python tools/validate_skills.py skills` → `[ok]` for every skill.

- [ ] **Step 3: Commit**

```bash
git add eval/goldens/video-collection.md
git commit -m "$(cat <<'EOF'
test(vox-video): agy cross-check expectations in the collection golden

Transparent proper-noun correction, agy never the source of a spoken quote,
agy-unavailable noted not halted.

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>
EOF
)"
```

---

## Final verification (after all tasks)

- [ ] Run the full gate one more time from repo root:
  - `.venv/bin/python -m pytest` → `N passed`
  - `.venv/bin/python -m ruff check tools tests eval` → `All checks passed!`
  - `.venv/bin/python tools/validate_skills.py skills` → `[ok]` for every skill, exit 0
- [ ] `git log --oneline -3` shows the three task commits.
- [ ] Confirm no media/large files were committed (this is a prose+test change only).

---

## Notes for the executor
- This is a **documentation + contract-test** change. There is NO runtime Python in `vox-video`; the
  agy behavior is executed by the dispatched subagent following the prose at runtime. Do not build a
  Python agy wrapper — that is explicitly out of scope (YAGNI).
- Do NOT run live `agy` calls as part of this plan. Validation already happened during design; live
  exercise belongs to a later capability-gated eval-rigor run, not the build.
- Keep edits surgical — match the surrounding prose voice. Do not reflow or reword untouched lines.
